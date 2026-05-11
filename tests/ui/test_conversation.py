from rich.text import Text

from elroy.io.formatters.rich_formatter import RichFormatter
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.ui.conversation import ConversationController


class _PromptHistoryStub:
    def load(self) -> list[str]:
        return []

    def append(self, text: str) -> None:
        del text


class _ConversationPaneStub:
    def __init__(self) -> None:
        self.renderables: list[object] = []

    def write_history(self, renderable) -> None:
        self.renderables.append(renderable)


def _formatter() -> RichFormatter:
    return RichFormatter(
        system_message_color="green",
        assistant_message_color="cyan",
        user_input_color="yellow",
        warning_color="red",
        internal_thought_color="dim",
    )


def test_render_existing_context_messages_formats_internal_thought_segments() -> None:
    controller = ConversationController(_formatter(), _PromptHistoryStub(), show_internal_thought=True)
    pane = _ConversationPaneStub()

    controller.render_existing_context_messages(
        pane,
        [
            ContextMessage(role="system", content="system", chat_model=None),
            ContextMessage(
                role="assistant",
                content="<internal_thought>Need to think</internal_thought>Visible answer",
                chat_model="test-model",
            ),
        ],
        bootstrap_tool_call_ids=set(),
    )

    assert pane.renderables == [
        Text("Need to think", style="italic dim"),
        Text("Visible answer", style="cyan"),
    ]


def test_render_existing_context_messages_hides_internal_thought_when_disabled() -> None:
    controller = ConversationController(_formatter(), _PromptHistoryStub(), show_internal_thought=False)
    pane = _ConversationPaneStub()

    controller.render_existing_context_messages(
        pane,
        [
            ContextMessage(role="system", content="system", chat_model=None),
            ContextMessage(
                role="assistant",
                content="<internal_thought>Need to think</internal_thought>Visible answer",
                chat_model="test-model",
            ),
        ],
        bootstrap_tool_call_ids=set(),
    )

    assert pane.renderables == [Text("Visible answer", style="cyan")]
