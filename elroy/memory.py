import logging
from functools import partial
from typing import List, Set, Tuple

from sqlmodel import select
from toolz import concat, pipe
from toolz.curried import filter, map, unique

from elroy.config import ElroyContext
from elroy.llm.client import query_llm_json
from elroy.llm.prompts import summarize_for_memory
from elroy.store.data_models import ContextMessage, Memory
from elroy.store.message import get_context_messages
from elroy.system.clock import get_utc_now
from elroy.system.parameters import CHAT_MODEL, MEMORY_WORD_COUNT_LIMIT
from elroy.tools.messenger import remove_from_context


def formulate_memory(user_preferred_name: str, context_messages: List[ContextMessage]) -> Tuple[str, str]:
    from elroy.system_context import format_context_messages

    return pipe(
        format_context_messages(user_preferred_name, context_messages),
        partial(summarize_for_memory, user_preferred_name),
    )  # type: ignore


def consolidate_memories(context: ElroyContext, memory1: Memory, memory2: Memory):
    if memory1.text == memory2.text:
        logging.info(f"Memories are identical, marking memory with id {memory2.id} as inactive.")
        memory2.is_active = False
        context.session.add(memory2)
        context.session.commit()
    else:

        logging.info("Consolidating memories '{}' and '{}'".format(memory1.name, memory2.name))
        response = query_llm_json(
            system="Your task is to consolidate or reorganize two pieces of text."
            "Each pice of text has a title and a main body. You should either combine the titles and the main bodies into a single title and main body, or create multiple title/text combinations with distinct information."
            f"The new bodies should not exceed {MEMORY_WORD_COUNT_LIMIT} words."
            "If referring to dates and times, use use ISO 8601 format, rather than relative references. It is critical that when applicable, specific absolute dates are retained."
            ""
            "If the two texts are redunant, but they together discuss distinct topics, you can create multiple new texts rather than just one."
            "One hint that multiple texts are warranted is if the title has the word 'and', and can reasonably be split into two titles."
            "Above all, ensure that each consolidate text has one basic topic, and that the text is coherent."
            "Return your response in JSON format, with the following structure:"
            "- REASONING: an explanation of your reasoning how you chose to consolidate or reorganize the texts. This must include information about what factored into your decision about whether to output one new texts, or multiple."
            "- NEW_TEXTS: Key to contain the new text or texts. This should be a list, each of which should have the following keys:"
            "   - TITLE: the title of the consolidated memory"
            "   - TEXT: the consolidated memory",
            prompt="\n".join(
                [
                    f"Title 1: {memory1.name}",
                    f"Text 1: {memory1.text}",
                    f"Title 2: {memory2.name}",
                    f"Text 2: {memory2.text}",
                ],
            ),
            model=CHAT_MODEL,
        )
        assert isinstance(response, dict)

        new_texts = response["NEW_TEXTS"]  # type: ignore

        if isinstance(new_texts, dict):
            new_texts = [new_texts]

        
        logging.info(f"REASONING: {response['REASONING']}") 

        new_ids = []
        for new_text in new_texts:
            new_name = new_text["TITLE"]
            new_text = new_text["TEXT"]

            assert new_name
            assert new_text
            new_ids.append(create_memory(context, new_name, new_text))

        logging.info(f"New memory id's = {new_ids}")

        logging.info(f"Consolidating into {len(new_texts)} new memories")
        logging.info(f"marked memory with id {memory1.id} and {memory2.id} as inactive.")

        mark_memory_inactive(context, memory1)
        mark_memory_inactive(context, memory2)


def mark_memory_inactive(context: ElroyContext, memory: Memory):
    memory.is_active = False
    context.session.add(memory)
    context.session.commit()
    remove_from_context(context, memory)


def create_memory(context: ElroyContext, name: str, text: str) -> int:
    memory = Memory(user_id=context.user_id, name=name, text=text)
    context.session.add(memory)
    context.session.commit()
    context.session.refresh(memory)
    from elroy.store.embeddings import upsert_embedding

    memory_id = memory.id
    assert memory_id

    upsert_embedding(context.session, memory)

    return memory_id


def get_memory_names(context: ElroyContext) -> Set[str]:
    """Fetch all active memories for the user"""
    memories = context.session.exec(
        select(Memory).where(
            Memory.user_id == context.user_id,
            Memory.is_active == True,
        )
    ).all()
    return {memory.name for memory in memories}


def get_relevant_memories(context: ElroyContext) -> List[str]:
    return pipe(
        get_context_messages(context),
        filter(lambda m: m.created_at_utc_epoch_secs > get_utc_now().timestamp() - context.config.max_in_context_message_age_seconds),
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
    )  # type: ignore
