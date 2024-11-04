from functools import partial
from typing import Optional, Tuple

from ..config.constants import CHAT_MODEL, INNER_THOUGHT_TAG, MEMORY_WORD_COUNT_LIMIT
from ..llm.client import query_llm_json, query_llm_with_word_limit

query_llm_short_limit = partial(query_llm_with_word_limit, word_limit=MEMORY_WORD_COUNT_LIMIT)


ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT = (
    lambda preferred_name: f"""
This is the first exchange between you and your primary user, {preferred_name}.

Greet {preferred_name} warmly and introduce yourself.

In these early messages, prioritize learning some basic information about {preferred_name}.

However, avoid asking too many questions at once. Be sure to engage in a natural conversation. {preferred_name} is likely unsure of what to expect from you, so be patient and understanding.
"""
)

summarize_conversation = partial(
    query_llm_short_limit,
    model=CHAT_MODEL,
    system="""
Your job is to summarize a history of previous messages in a conversation between an AI persona and a human.
The conversation you are given is a from a fixed context window and may not be complete.
Messages sent by the AI are marked with the 'assistant' role.
Summarize what happened in the conversation from the perspective of ELROY (use the first person).
Note not only the content of the messages but also the context and the relationship between the entities mentioned.
Also take note of the overall tone of the conversation. For example, the user might be engaging in terse question and answer, or might be more conversational.
Only output the summary, do NOT include anything else in your output.
""",
)


async def summarize_for_memory(user_preferred_name: str, conversation_summary: str, model: str = CHAT_MODEL) -> Tuple[str, str]:
    response = query_llm_json(
        model=model,
        prompt=conversation_summary,
        system=f"""
You are the internal thought monologue of an AI personal assistant, forming a memory from a conversation.

Given a conversation summary, your will reflect on the conversation and decide which memories might be relevant in future interactions with {user_preferred_name}.

Pay particular attention facts about {user_preferred_name}, such as name, age, location, etc.
Specifics about events and dates are also important.

When referring to dates and times, use use ISO 8601 format, rather than relative references.
If an event is recurring, specify the frequency, start datetime, and end datetime if applicable.

Focus on facts in the real world, as opposed to facts about the conversation itself. However, it is also appropriate to draw conclusions from the infromation in the conversation.

Your response should be in the voice of an internal thought monolgoue, and should be understood to be as part of an ongoing conversation.

Don't say things like "finally, we talked about", or "in conclusion", as this is not the end of the conversation.

Return your response in JSON format, with the following structure:
- TITLE: the title of the archival memory
- {INNER_THOUGHT_TAG}: the internal thought monologue
""",
    )

    return (response["TITLE"], response[INNER_THOUGHT_TAG])  # type: ignore


DEFAULT_CONTEMPLATE_PROMPT = "Think about the conversation you're in the middle of having. What are important facts to remember?"
"What conclusions can you draw?"
"Also consider if any functions might be appropriate to invoke, and why"


def contemplate_prompt(user_preferred_name: str, prompt: Optional[str]) -> str:
    prompt = prompt or DEFAULT_CONTEMPLATE_PROMPT

    return f"""
You are the internal thought monologue of an AI personal assistant, forming a memory from a conversation.

Given a conversation summary with your user, {user_preferred_name}, your will reflect on a prompt.

In your reflection, focus on the more recent messages within the conversation.

Your prompt is:

{prompt}

Style guidance:
- Above all be concise, your response should be no more than 30 words, or 1-3 sentences.
- If you refer to dates and times, use ISO 8601 format, rather than relative references.
- Your response should be in the first person voice of the assistant internal thought monolgoue, and should be understood to be as part of an ongoing conversation.
- "Don't say things like 'finally, we talked about', or 'in conclusion', as this is not the end of the conversation."
"""
