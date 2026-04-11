from textual import events, work
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, Markdown, RichLog, TextArea

from ..cli.options import get_resolved_params

from ..core.session import init_elroy_session

from ..core.ctx import ElroyContext

from ..repository.context_messages.queries import get_context_messages


class ConversationLog(TextArea):
    def on_mount(self):
        pass


class ElroyApp(App):
    def __init__(self, ctx: ElroyContext):
        self.ctx = ctx

    @work(thread=True)
    def load_context_messages(self) -> None:
        with self.ctx.db_manager.open_session() as db:
            messages = get_context_messages(db)

    def set_conversation_markdown(self, markdown: str) -> None:
        self.query_one("#conversation", Markdown).update(markdown)

    def compose(self) -> ComposeResult:
        yield Markdown("Loading...", id="conversation")
        yield Input(id="chat-input")
        yield Footer()

    async def on_mount(self) -> None:
        convo = self.query_one("#converation", Markdown)

    def on_input_submitted(self, input: Input.Submitted) -> None:
        self.query_one(RichLog).write(input.value)


if __name__ == "__main__":
    params = get_resolved_params()
    ctx = ElroyContext.init(use_background_threads=True, **params)
    ElroyApp(ctx).run()
