import pytest

from elroy.core.constants import ASSISTANT, InvalidForceToolError
from elroy.core.session import open_turn_context
from elroy.messenger.messenger import process_message
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.memories.queries import get_active_memories
from elroy.repository.user.queries import do_get_user_preferred_name
from elroy.repository.user.session import build_user_session
from elroy.repository.user.tools import set_user_preferred_name
from tests.utils import process_test_message


@pytest.mark.flaky(reruns=3)
def test_hello_world(ctx):
    # Test message
    test_message = "Hello, World!"

    # Get the argument passed to the delivery function
    response = process_test_message(ctx, test_message)

    # Assert that the response is a non-empty string
    assert isinstance(response, str)
    assert len(response) > 0

    # Assert that the response contains a greeting
    assert any(greeting in response.lower() for greeting in ["hello", "hi", "greetings"])


def test_force_tool(ctx):
    process_test_message(ctx, "Jimmy", set_user_preferred_name.__name__)
    with open_turn_context(ctx) as turn:
        user_session = build_user_session(turn)
        assert do_get_user_preferred_name(user_session.db.session, user_session.user_id) == "Jimmy"


def test_force_invalid_tool(ctx):
    with pytest.raises(InvalidForceToolError):
        process_test_message(ctx, "Jimmy", "invalid_tool")


def test_no_base_tools(ctx):
    ctx.include_base_tools = False

    process_test_message(ctx, "Please create a memory: today I went swimming")
    assert len(get_active_memories(ctx)) == 0


def test_base_tools(ctx):
    process_test_message(ctx, "Please create a memory: today I went swimming")
    assert len(get_active_memories(ctx)) == 1


def test_process_message_can_skip_persisting_input_message(ctx, monkeypatch):
    def fake_maybe_recall_memories(self, msg, context_messages, new_msgs):
        del self, msg, context_messages, new_msgs
        if False:
            yield None

    def fake_append_due_items(self, new_msgs):
        del self, new_msgs

    def fake_run_llm_loop(self, context_messages, new_msgs, enable_tools, force_tool, persist_input_message):
        del context_messages, enable_tools, force_tool
        new_msgs.append(
            ContextMessage(role=ASSISTANT, content="Restarted successfully. Ready to continue.", chat_model=ctx.chat_model.name)
        )
        self.context_refresh_orchestrator.add_context_messages(self._messages_to_persist(new_msgs, persist_input_message))
        if False:
            yield None

    monkeypatch.setattr("elroy.core.conversation_orchestrator.ConversationOrchestrator._maybe_recall_memories", fake_maybe_recall_memories)
    monkeypatch.setattr("elroy.core.conversation_orchestrator.ConversationOrchestrator._append_due_items", fake_append_due_items)
    monkeypatch.setattr("elroy.core.conversation_orchestrator.ConversationOrchestrator._run_llm_loop", fake_run_llm_loop)

    with open_turn_context(ctx) as turn:
        list(
            process_message(
                role="user",
                ctx=ctx,
                session=turn.session,
                msg="Elroy just restarted. Send a brief message that you are back and ready to continue.",
                enable_tools=False,
                persist_input_message=False,
            )
        )

    messages = list(get_context_messages(ctx))
    assert not any(
        message.role == "user" and message.content == "Elroy just restarted. Send a brief message that you are back and ready to continue."
        for message in messages
    )
    assert any(message.role == ASSISTANT and message.content == "Restarted successfully. Ready to continue." for message in messages)
