import logging
from contextlib import contextmanager
from itertools import product
from typing import Iterator, List, Union

from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.completion import Completion, WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style as PTKStyle
from pygments.lexers.special import TextLexer
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.text import Text
from toolz import concatv, pipe
from toolz.curried import map

from ..config.constants import EXIT
from ..config.paths import get_prompt_history_path
from ..db.db_models import FunctionCall, Goal, Memory
from ..io.base import ElroyIO
from ..llm.stream_parser import AssistantInternalThought, TextOutput
from ..repository.context_messages.data_models import ContextMessage
from .formatters.rich_formatter import RichFormatter


class SlashCompleter(WordCompleter):
    def get_completions(self, document, complete_event):  # noqa F811
        text = document.text
        if not text.startswith("/"):
            return

        words = text.split()

        exact_cmd_prefix = False
        # If we just have "/" or are typing the command part
        if len(words) <= 1:
            cmds = {c.split()[0] for c in self.words}  # type: ignore # Get just the command parts
            for cmd in cmds:
                if cmd.startswith(text) and text != cmd:
                    yield Completion(cmd, start_position=-len(text))
                    exact_cmd_prefix = True
            if exact_cmd_prefix:
                return

        # If we have a command and are typing arguments
        cmd = words[0]
        # Get the full command templates that start with this command
        matching_commands = [w for w in self.words if w.startswith(cmd)]  # type: ignore
        if matching_commands:
            # Create a completer just for the arguments of this command
            arg_text = " ".join(words[1:])
            # Extract just the argument parts from the matching commands
            arg_options = [" ".join(m.split()[1:]) for m in matching_commands if len(m.split()) > 1]
            if arg_options:
                # Complete from the start of the argument portion
                arg_start_position = -len(arg_text) if arg_text else 0
                for arg in arg_options:
                    if arg.startswith(arg_text):
                        yield Completion(arg, start_position=arg_start_position)


class CliIO(ElroyIO):
    def __init__(
        self,
        formatter: RichFormatter,
        show_internal_thought: bool,
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

    def print_stream(self, messages: Iterator[Union[TextOutput, RenderableType, FunctionCall]]) -> None:
        try:
            with self.status():
                first_msg = next(messages, None)
            if first_msg:
                self.print(first_msg, end="")
            for message in messages:
                self.print(message, end="")
        except KeyboardInterrupt:
            pass
        finally:
            self.console.print()

    def print(self, message: Union[TextOutput, RenderableType, FunctionCall], end: str = "\n") -> None:
        if isinstance(message, AssistantInternalThought) and not self.show_internal_thought:
            logging.debug(f"Internal thought: {message.content}")
            return

        if not self.last_output_type and isinstance(message, TextOutput):
            message.content = message.content.lstrip()
        elif not self.last_output_type == type(message):
            self.console.print("\n\n", end="")

        for output in self.formatter.format(message):
            self.console.print(output, end=end)
            self.last_output_type = type(message)

    def print_memory_panel(self, titles: List[str]):
        if titles:
            panel = Panel("\n".join(titles), title="Relevant Context", expand=False, border_style=self.user_input_color)
            self.console.print(panel)

    def rule(self):
        self.last_output_type = None
        self.console.rule(style=self.user_input_color)

    async def prompt_user(self, retries: int, prompt=">", prefill: str = "", keyboard_interrupt_count: int = 0) -> str:
        try:
            return await self._prompt_user(prompt, prefill)
        except KeyboardInterrupt:
            keyboard_interrupt_count += 1
            if keyboard_interrupt_count >= retries:
                raise EOFError
            elif keyboard_interrupt_count == 2:
                self.info("To exit, type /exit, exit, or press Ctrl-D.")
            return await self.prompt_user(retries, prompt, prefill, keyboard_interrupt_count)

    async def _prompt_user(self, prompt=">", prefill: str = "") -> str:
        return await self.prompt_session.prompt_async(HTML(f"<b>{prompt} </b>"), default=prefill, style=self.style)

    def update_completer(self, goals: List[Goal], memories: List[Memory], context_messages: List[ContextMessage]) -> None:
        from ..repository.recall.queries import is_in_context
        from ..tools.tools_and_commands import (
            ALL_ACTIVE_GOAL_COMMANDS,
            ALL_ACTIVE_MEMORY_COMMANDS,
            IN_CONTEXT_GOAL_COMMANDS,
            IN_CONTEXT_MEMORY_COMMANDS,
            NON_ARG_PREFILL_COMMANDS,
            NON_CONTEXT_GOAL_COMMANDS,
            NON_CONTEXT_MEMORY_COMMANDS,
            USER_ONLY_COMMANDS,
        )

        in_context_goal_names = sorted([g.get_name() for g in goals if is_in_context(context_messages, g)])
        non_context_goal_names = sorted([g.get_name() for g in goals if g.get_name() not in in_context_goal_names])

        in_context_memories = sorted([m.get_name() for m in memories if is_in_context(context_messages, m)])
        non_context_memories = sorted([m.get_name() for m in memories if m.get_name() not in in_context_memories])

        self.prompt_session.completer = pipe(  # type: ignore # noqa F841
            concatv(
                product(IN_CONTEXT_GOAL_COMMANDS, in_context_goal_names),
                product(NON_CONTEXT_GOAL_COMMANDS, non_context_goal_names),
                product(ALL_ACTIVE_GOAL_COMMANDS, [g.get_name() for g in goals]),
                product(IN_CONTEXT_MEMORY_COMMANDS, in_context_memories),
                product(NON_CONTEXT_MEMORY_COMMANDS, non_context_memories),
                product(ALL_ACTIVE_MEMORY_COMMANDS, [m.get_name() for m in memories]),
            ),
            map(lambda x: f"/{x[0].__name__} {x[1]}"),
            list,
            lambda x: x + [f"/{f.__name__}" for f in NON_ARG_PREFILL_COMMANDS | USER_ONLY_COMMANDS],
            ["/" + EXIT].__add__,
            lambda x: SlashCompleter(words=x),  # type: ignore
        )
