# Triage input, creating either a memory or a due item

from pydantic import BaseModel
from toolz import concat, juxt, pipe
from toolz.curried import filter

from ..core.constants import RecoverableToolError
from ..core.ctx import ElroyConfig
from ..core.logging import get_logger
from ..core.session import run_with_turn
from ..core.turn import TurnContext
from ..db.db_models import AgendaItem, EmbeddableSqlModel, Memory
from ..utils.clock import local_now, utc_now
from .data_models import CreateDueItemRequest, CreateMemoryRequest
from .memo_runtime import build_memo_runtime
from .memories.factory import build_memory_lifecycle_orchestrator
from .memories.queries import filter_for_relevance
from .recall.queries import do_get_most_relevant_due_items, do_get_most_relevant_memories
from .reminders.factory import build_reminder_orchestrator

logger = get_logger()


def do_augment_text(turn: TurnContext, text: str) -> str:
    runtime = build_memo_runtime(turn)
    memories: list[EmbeddableSqlModel] = pipe(
        text,
        runtime.llm.get_embedding,
        lambda x: juxt(do_get_most_relevant_memories, do_get_most_relevant_due_items)(turn, x),
        concat,
        list,
        filter(lambda x: x is not None),
        list,
        lambda mems: filter_for_relevance(
            runtime.fast_llm,
            text,
            mems,
            lambda m: m.to_fact(),
        ),
        list,
    )

    if len(memories) > 0:
        mem_str = "\n".join([m.to_fact() for m in memories])
        return runtime.llm.query_llm(
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

    return text


def augment_text(ctx: ElroyConfig, text: str) -> str:
    return run_with_turn(ctx, do_augment_text, text)


def ingest_memo(ctx: ElroyConfig, text: str) -> list[Memory | AgendaItem]:
    def _inner(turn: TurnContext, text: str, attempt: int = 1, prev_attempt_error_info: str | None = None) -> list[Memory | AgendaItem]:
        try:
            runtime = build_memo_runtime(turn)

            class MemoResponse(BaseModel):
                create_due_item_request: CreateDueItemRequest | None = None
                create_memory_request: CreateMemoryRequest | None = None

            augmented = do_augment_text(turn, text)

            req = runtime.llm.query_llm_with_response_format(
                system=(
                    f"""Your task is to convert text into either a due item or a memory.

                A memory is a generic note, without a specific time or context that it should be recalled.

                A due item is similar to a memory, but it should be something the user wants or needs to surface in a specific context or time.

                Where possible, convert any relative dates or times to ISO 8601 format. Note the local time is {local_now()}, or {utc_now()} UTC.

                If creating a due item with a trigger_time, note that due items cannot be created for time in the past.

                You should provide EITHER a create_due_item_request OR a create_memory_request, not both.
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
            if req.create_memory_request or req.create_due_item_request:
                if req.create_memory_request:
                    logger.info("Creating memory")
                    resp.append(
                        build_memory_lifecycle_orchestrator(turn).do_create_memory(
                            req.create_memory_request.name,
                            req.create_memory_request.text,
                            [],
                            True,
                        )
                    )
                if req.create_due_item_request:
                    logger.info("Creating due item")
                    resp.append(
                        build_reminder_orchestrator(turn).do_create_due_item(
                            req.create_due_item_request.name,
                            req.create_due_item_request.text,
                            req.create_due_item_request.trigger_datetime,
                            req.create_due_item_request.trigger_context,
                        )
                    )
            return resp
        except RecoverableToolError as e:
            if attempt >= 3:
                logger.warning(f"Abandoinging ingest_memo after {attempt} attempts", exc_info=True)
                raise
            attempt += 1
            return _inner(turn, text, attempt, f"A previous attempt at this task failed with error: {e!s}")

    return run_with_turn(ctx, _inner, text, 1, None)
