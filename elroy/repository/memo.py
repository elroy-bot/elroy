# Triage input, creating either a memory or a reminder


from typing import List, Optional, Union

from pydantic import BaseModel
from toolz import concat, juxt, pipe
from toolz.curried import filter

from ..core.constants import RecoverableToolError
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..db.db_models import EmbeddableSqlModel, Memory, Reminder
from ..models import CreateMemoryRequest, CreateReminderRequest
from ..utils.clock import local_now, utc_now
from .memories.operations import do_create_memory
from .memories.queries import filter_for_relevance
from .recall.queries import get_most_relevant_memories, get_most_relevant_reminders
from .reminders.operations import do_create_reminder

logger = get_logger()


def augment_text(ctx: ElroyContext, text: str) -> str:
    memories: List[EmbeddableSqlModel] = pipe(
        text,
        ctx.llm.get_embedding,
        lambda x: juxt(get_most_relevant_memories, get_most_relevant_reminders)(ctx, x),
        concat,
        list,
        filter(lambda x: x is not None),
        list,
        lambda mems: filter_for_relevance(
            ctx.fast_llm,
            text,
            mems,
            lambda m: m.to_fact(),
        ),
        list,
    )

    if len(memories) > 0:
        mem_str = "\n".join([m.to_fact() for m in memories])
        return ctx.llm.query_llm(
            system=f"""
            Your job is to augment text with contextual information recalled from memory. You will be provided with the initial text, as well as memories from storage which have been deemed to be relevant. Use this information to augment the text with enough context such that future readers can better understand the memory.

            This could include information about how subjects relate to the user.

            If there is still unknown information, simply omit that context, do not add any content about how you don't know.

            Respond with both augmented text, and a short title for the memory.

            Translate relative dates to ISO 8601 format, where possible. Note that the current datetime is: {local_now()}
            """,
            prompt=f"""
            # Original Text

            {text}

            # Relevant memories

            {mem_str}
            """,
        )

    else:
        return text


def do_ingest_memo(ctx: ElroyContext, text: str) -> List[Union[Reminder, Memory]]:  # noqa F841
    def _inner(
        ctx: ElroyContext, text: str, attempt: int = 1, prev_attempt_error_info: Optional[str] = None
    ) -> List[Union[Reminder, Memory]]:
        try:

            class MemoResponse(BaseModel):
                create_reminder_request: Optional[CreateReminderRequest] = None
                create_memory_request: Optional[CreateMemoryRequest] = None

            augmented = augment_text(ctx, text)

            req = ctx.llm.query_llm_with_response_format(
                system=(
                    f"""Your task is to convert text into either a reminder or a memory.

                A memory is a generic note, without a specific time or context that it should be recalled.

                A reminder is similar to a memory, but it should be something the user wants or needs to remember in a specific context or time.

                Where possible, convert any relative dates or times to ISO 8601 format. Note the local time is {local_now()}, or {utc_now()} UTC.

                If creating a reminder with a trigger_time, note that reminders cannot be created for time in the past.

                You should provide EITHER a create_reminder_request OR a create_memory_request, not both.
                Set the field you don't need to null.
                """
                    + f"\n\n{prev_attempt_error_info}"
                    if prev_attempt_error_info
                    else ""
                ),
                prompt=augmented,
                response_format=MemoResponse,
            )

            resp = []

            if req.create_memory_request:
                logger.info("Creating memory")
                resp.append(
                    do_create_memory(
                        ctx,
                        req.create_memory_request.name,
                        req.create_memory_request.text,
                        [],
                        True,
                    )
                )
            if req.create_reminder_request:
                logger.info("Creating reminder")
                resp.append(
                    do_create_reminder(
                        ctx,
                        req.create_reminder_request.name,
                        req.create_reminder_request.text,
                        req.create_reminder_request.trigger_datetime,
                        req.create_reminder_request.reminder_context,
                    )
                )
            return resp
        except RecoverableToolError as e:
            if attempt >= 3:
                logger.warning(f"Abandoinging ingest_memo after {attempt} attempts", exc_info=True)
                raise
            else:
                attempt += 1
                return _inner(ctx, text, attempt, f"A previous attempt at this task failed with error: {str(e)}")

    return _inner(ctx, text, 1, None)
