from typing import Optional, Tuple

from ..config.llm import ChatModel
from ..core.constants import MEMORY_WORD_COUNT_LIMIT
from ..core.tracing import tracer
from ..llm.client import query_llm, query_llm_with_word_limit
from ..llm.parsing import extract_title_and_body

ONBOARDING_SUPPLEMENT_INSTRUCT = (
    lambda preferred_name: f"""
This is the first exchange between you and your primary user, {preferred_name}.

Greet {preferred_name} warmly and introduce yourself.

In these early messages, prioritize learning some basic information about {preferred_name}.

However, avoid asking too many questions at once. Be sure to engage in a natural conversation. {preferred_name} is likely unsure of what to expect from you, so be patient and understanding.
"""
)


@tracer.chain
def summarize_conversation(model: ChatModel, assistant_name: str, convo_summary: str) -> str:
    return query_llm_with_word_limit(
        model=model,
        prompt=convo_summary,
        word_limit=MEMORY_WORD_COUNT_LIMIT,
        system=f"""
Your job is to summarize a history of previous messages in a conversation between an AI persona and a human.
The conversation you are given is a from a fixed context window and may not be complete.
Messages sent by the AI are marked with the 'assistant' role.
Summarize what happened in the conversation from the perspective of {assistant_name} (use the first person).
Note not only the content of the messages but also the context and the relationship between the entities mentioned.
Also take note of the overall tone of the conversation. For example, the user might be engaging in terse question and answer, or might be more conversational.
Only output the summary, do NOT include anything else in your output.
""",
    )


@tracer.chain
def summarize_for_memory(model: ChatModel, conversation_summary: str, user_preferred_name: Optional[str]) -> Tuple[str, str]:
    user_noun = user_preferred_name or "the user"

    response = query_llm(
        model=model,
        prompt=conversation_summary,
        system=f"""
You are the internal thought monologue of an AI personal assistant, forming a memory from a conversation.

Given a conversation summary, your will reflect on the conversation and decide which memories might be relevant in future interactions with {user_preferred_name}.

Pay particular attention facts about {user_noun}, such as name, age, location, etc.
Specifics about events and dates are also important.

When referring to dates and times, use use ISO 8601 format, rather than relative references.
If an event is recurring, specify the frequency, start datetime, and end datetime if applicable.

Focus on facts in the real world, as opposed to facts about the conversation itself. However, it is also appropriate to draw conclusions from the infromation in the conversation.

Your response should be in the voice of an internal thought monolgoue, and should be understood to be as part of an ongoing conversation.

Don't say things like "finally, we talked about", or "in conclusion", as this is not the end of the conversation.

Respond in markdown format. The first line should be a title line, and the rest of the response should be the content of the memory.

An example response might look like this:

# Exercise progress on 2021-01-01
Today, {user_noun} went for a 5 mile run. They plan to run a marathon in the spring.

""",
    )

    return extract_title_and_body(response)
