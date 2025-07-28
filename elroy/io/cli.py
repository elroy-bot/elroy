from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from itertools import product
from typing import Iterable, List

from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style as PTKStyle
from pygments.lexers.special import TextLexer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from toolz import concatv, pipe
from toolz.curried import map

from elroy.io.completer import SlashCompleter

from ..config.paths import get_prompt_history_path
from ..core.constants import EXIT
from ..core.logging import get_logger
from ..db.db_models import Memory
from ..io.base import ElroyIO
from ..llm.stream_parser import AssistantInternalThought, TextOutput
from ..repository.context_messages.data_models import ContextMessage
from .formatters.base import ElroyPrintable
from .formatters.rich_formatter import RichFormatter

logger = get_logger()


class CliIO(ElroyIO):
    def __init__(
        self,
        formatter: RichFormatter,
        show_internal_thought: bool,
        show_memory_panel: bool,
    ) -> None:
        self.console = Console()
        self.formatter = formatter
        self.user_input_color = formatter.user_input_color
        self.show_internal_thought = show_internal_thought
        self.style = PTKStyle.from_dict(
            {
                "prompt": "bold",
                "user-input": self.user_input_color + " bold",
                "": self.user_input_color,
                "pygments.literal.string": f"bold italic {self.user_input_color}",
            }
        )

        self.prompt_session = PromptSession(
            history=FileHistory(get_prompt_history_path()),
            style=self.style,
            lexer=PygmentsLexer(TextLexer),
        )
        self.show_memory_panel = show_memory_panel

        self.last_output_type = None

    @contextmanager
    def status(self, message: str = ""):
        """Context manager for status messages with spinner."""
        with self.console.status(
            Text(message, style=self.formatter.internal_thought_color),
            spinner="squareCorners",
            spinner_style=self.formatter.internal_thought_color,
        ):
            yield

    def print_stream(self, messages: Iterable[ElroyPrintable]) -> None:
        try:
            with self.status():
                first_msg = next(iter(messages), None)
            if first_msg:
                self.print(first_msg, end="")
            for message in messages:
                self.print(message, end="")
        except KeyboardInterrupt:
            pass
        finally:
            self.console.print()

    def print(self, message: ElroyPrintable, end: str = "\n") -> None:
        if isinstance(message, AssistantInternalThought) and not self.show_internal_thought:
            logger.debug(f"Internal thought: {message}")
            return

        if not self.last_output_type and isinstance(message, TextOutput):
            message.content = message.content.lstrip()
        elif self.last_output_type and not self.last_output_type == type(message):
            self.console.print("\n\n", end="")

        for output in self.formatter.format(message):
            self.console.print(output, end=end)
            self.last_output_type = type(message)

    def print_memory_panel(self, titles: Iterable[str]):
        if titles:
            panel = Panel("\n".join(titles), title="Relevant Context", expand=False, border_style=self.user_input_color)
            self.console.print(panel)

    def rule(self):
        self.last_output_type = None
        self.console.rule(style=self.user_input_color)

    def prompt_user(
        self, thread_pool: ThreadPoolExecutor, retries: int, prompt=">", prefill: str = "", keyboard_interrupt_count: int = 0
    ) -> str:
        from ..utils.utils import run_async

        try:
            return run_async(thread_pool, self._prompt_user(prompt, prefill))
        except KeyboardInterrupt:
            keyboard_interrupt_count += 1
            if keyboard_interrupt_count >= retries:
                raise EOFError
            elif keyboard_interrupt_count == 2:
                self.info("To exit, type /exit, exit, or press Ctrl-D.")
            return self.prompt_user(thread_pool, retries, prompt, prefill, keyboard_interrupt_count)

    async def _prompt_user(self, prompt=">", prefill: str = "") -> str:
        return await self.prompt_session.prompt_async(HTML(f"<b>{prompt} </b>"), default=prefill, style=self.style)

    def update_completer(self, memories: List[Memory], reminders: List, context_messages: List[ContextMessage]) -> None:
        from ..repository.recall.queries import is_in_context
        from ..tools.tools_and_commands import (
            ALL_ACTIVE_MEMORY_COMMANDS,
            ALL_ACTIVE_REMINDER_COMMANDS,
            IN_CONTEXT_MEMORY_COMMANDS,
            NON_ARG_PREFILL_COMMANDS,
            NON_CONTEXT_MEMORY_COMMANDS,
            USER_ONLY_COMMANDS,
        )

        in_context_memories = sorted([m.get_name() for m in memories if is_in_context(context_messages, m)])
        non_context_memories = sorted([m.get_name() for m in memories if m.get_name() not in in_context_memories])

        reminder_names = sorted([r.get_name() for r in reminders])

        self.prompt_session.completer = pipe(  # type: ignore # noqa F841
            concatv(
                product(IN_CONTEXT_MEMORY_COMMANDS, in_context_memories),
                product(NON_CONTEXT_MEMORY_COMMANDS, non_context_memories),
                product(ALL_ACTIVE_MEMORY_COMMANDS, [m.get_name() for m in memories]),
                product(ALL_ACTIVE_REMINDER_COMMANDS, reminder_names),
            ),
            map(lambda x: f"/{x[0].__name__} {x[1]}"),
            list,
            lambda x: x + [f"/{f.__name__}" for f in NON_ARG_PREFILL_COMMANDS | USER_ONLY_COMMANDS],
            ["/" + EXIT, "/help"].__add__,
            lambda x: SlashCompleter(words=x),  # type: ignore
        )
