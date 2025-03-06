from typing import Callable, List

from smolagents import LiteLLMModel, Tool, ToolCallingAgent

from elroy.api import Elroy
from elroy.core.session import dbsession
from elroy.core.tracing import tracer
from elroy.repository.memories.tools import examine_memories


class ExamineMemoryTool(Tool):
    name = "examine_memories"
    description = """"Search through memories for the answer to a question.

    This function searches summarized memories and goals. Each memory also contains source information.

    If a retrieved memory is relevant but lacks detail to answer the question, use the get_source_content_for_memory tool. This can be useful in cases where broad information about a topic is provided, but more exact recollection is necessary."""
    inputs = {"question": {"type": "string", "description": "The question to search for the answer for in memories"}}
    output_type = "array"

    def __init__(self, ai: Elroy):
        self.ai = ai
        super().__init__()

    def forward(self, question: str):
        with dbsession(self.ai.ctx):
            return examine_memories(self.ai.ctx, question)


@tracer.agent
def force_tool_answer(ai: Elroy, question: str) -> str:

    ai.message(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
        force_tool="examine_memories",
    )

    return ai.message(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
    )


@tracer.agent
def smol_agent_answer(ai: Elroy, question: str) -> str:
    model = LiteLLMModel(
        model_id=ai.ctx.chat_model.name,
        api_base=ai.ctx.chat_model.api_base,
    )
    agent = ToolCallingAgent(tools=[ExamineMemoryTool(ai)], model=model)
    return agent.run(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
    )  # type: ignore


@tracer.agent
def just_answer(ai: Elroy, question: str) -> str:
    return ai.message(
        f"""The following is a test of your memory.
            Just give your answer, do not continue the conversation.
            E.g. if the question is: What is 2+2? Respond simply with: 4.
            Use tools to search for information!
            If you don't know even after using tools, say if you don't know say I don't know.:
            {question}""",
    )


ANSWER_FUNCS: List[Callable[[Elroy, str], str]] = [
    just_answer,
    smol_agent_answer,
    force_tool_answer,
]


def get_answer_func(name: str):
    for func in ANSWER_FUNCS:
        if func.__name__ == name:
            return func
    raise ValueError(f"Unknown answer function: {name}")
