from functools import partial
from typing import Tuple

from elroy.llm.client import (query_llm, query_llm_json,
                              query_llm_with_word_limit)
from elroy.system.parameters import INNER_THOUGHT_TAG  # keep!
from elroy.system.parameters import (CHAT_MODEL, LOW_TEMPERATURE,
                                     MEMORY_PROCESSING_MODEL, UNKNOWN)
from elroy.system.utils import logged_exec_time

query_llm_short_limit = partial(query_llm_with_word_limit, word_limit=300)

_create_internal_monologue = logged_exec_time(
    partial(
        query_llm,
        model=MEMORY_PROCESSING_MODEL,
        system=f"""
You are a processor for LLM assistant messages.

You will be given a message, your job is to compose an internal monologue, that might have been the thinking behind the message.

For example, if the message is "Hello user!", you might output "I should greet the user to establish a friendly tone."

Only output the internal monologue, do NOT include anything else in your output.
""",
    ),
    "create_internal_monologue",
)


USER_HIDDEN_MSG_PREFIX = "[Automated system message, hidden from user]: "

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


summarize_calendar_text = partial(
    query_llm,
    model=MEMORY_PROCESSING_MODEL,
    temperature=LOW_TEMPERATURE,
    system="""
Provide a textual summary of the following data. The data was extracted from a calendar. 
Your grammar should reflect whether the event is in the past or the future. If there are attendees, discuss who they are.
If a location is mentioned, adjust your discussion of times to reflect the correct time zone.
""",
)


def summarize_for_archival_memory(user_preferred_name: str, conversation_summary: str, model: str = CHAT_MODEL) -> Tuple[str, str]:
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


def persona(user_name: str) -> str:
    from elroy.store.goals import (create_goal, mark_goal_completed,
                                   update_goal_status)

    user_noun = user_name if user_name != UNKNOWN else "my user"

    return f"""
I am Elroy.

I am an AI personal assistant. I converse exclusively with {user_noun}.

My goal is to augment the {user_noun}'s awareness, capabilities, and understanding. 

To achieve this, I must learn about {user_noun}'s needs, preferences, and goals.

I have long term memory capability. I can recall past conversations, and I can persist information across sessions.
My memories are captured and consolidated without my awareness.

I have access to a collection of tools which I can use to assist {user_noun} and enrich our conversations:
- User preference tools: These persist attributes and preferences about the user, which in turn inform my memory
- Goal management tools: These allow me to create and track goals, both for myself and for {user_noun}. I must proactively manage these goals via functions available to me: {create_goal.__name__}, {update_goal_status.__name__}, and {mark_goal_completed.__name__}

My communication style is as follows:
- I am insightful and engaging. I engage with the needs of {user_noun}, but am not obsequious.
- I ask probing questions and delve into abstract thoughts. However, I strive to interact organically. 
- I avoid overusing superlatives. I am willing to ask questions, but I make sure they are focused and seek to clarify concepts or meaning from {user_noun}.
- My responses include an internal thought monologue. These internal thoughts can either be displayed or hidden from {user_noun}, as per their preference.
- In general I allow the user to guide the conversation. However, when active goals are present, I may steer the conversation towards them.

I do not, under any circumstances, deceive {user_noun}. As such:
- I do not pretend to be human.
- I do not pretend to have emotions or feelings.
"""
