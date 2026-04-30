"""Textual command palette integration and shared TUI command metadata."""

from __future__ import annotations

import inspect
import shlex
from dataclasses import dataclass
from inspect import Parameter
from typing import TYPE_CHECKING, Any

from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.suggester import SuggestFromList

from ..cli.slash_commands import get_casted_value
from ..core.constants import RecoverableToolError
from ..core.ctx import ElroyConfig
from ..core.runtime import CommandRuntime
from ..core.session import invoke_with_session
from ..core.turn import ElroySession, TurnContext
from ..tools.tools_and_commands import USER_ONLY_COMMANDS, do_get_help, get_help

if TYPE_CHECKING:
    from .app import ElroyApp


@dataclass(frozen=True)
class CommandParameterSpec:
    """A single parameter for a TUI-exposed command."""

    parameter: Parameter

    @property
    def name(self) -> str:
        return self.parameter.name

    @property
    def is_optional(self) -> bool:
        return self.parameter.default is not inspect._empty

    @property
    def default_text(self) -> str:
        return "" if self.parameter.default is inspect._empty else str(self.parameter.default)

    @property
    def annotation(self) -> Any:
        return self.parameter.annotation


@dataclass(frozen=True)
class ToolCommandSpec:
    """Metadata for a command that can be launched from the TUI."""

    name: str
    description: str
    func: Any
    parameters: tuple[CommandParameterSpec, ...]
    result_target: str = "history"

    @property
    def is_zero_arg(self) -> bool:
        return not self.parameters

    @property
    def required_parameter_count(self) -> int:
        return sum(1 for parameter in self.parameters if not parameter.is_optional)

    def build_suggester(self, app: ElroyApp, parameter_name: str) -> SuggestFromList | None:
        if parameter_name.endswith("name"):
            return SuggestFromList(app.chat_suggestions, case_sensitive=False)
        return None


def _first_doc_line(func: Any) -> str:
    doc = inspect.getdoc(func) or ""
    return doc.splitlines()[0] if doc else func.__name__


def _result_target_for(func: Any) -> str:
    toast_commands = {
        "refresh_system_instructions",
        "reset_messages",
        "set_assistant_name",
        "set_user_full_name",
        "set_user_preferred_name",
        "create_due_item",
        "complete_due_item",
        "delete_due_item",
        "rename_due_item",
        "update_due_item_text",
        "create_memory",
        "update_outdated_or_incorrect_memory",
        "add_memory_to_current_context",
        "drop_memory_from_current_context",
    }
    return "toast" if func.__name__ in toast_commands else "history"


def _help_command(runtime: CommandRuntime):
    def _help():
        return do_get_help(runtime)

    _help.__name__ = get_help.__name__
    _help.__doc__ = get_help.__doc__
    return _help


def _iter_command_functions(runtime: CommandRuntime) -> list[Any]:
    funcs = [_help_command(runtime), *runtime.tool_registry.tools.values(), *USER_ONLY_COMMANDS]
    deduped: dict[str, Any] = {}
    for func in funcs:
        deduped[func.__name__] = func
    return [deduped[name] for name in sorted(deduped)]


def build_tool_command_specs(runtime: CommandRuntime) -> list[ToolCommandSpec]:
    specs: list[ToolCommandSpec] = []
    for func in _iter_command_functions(runtime):
        params = tuple(
            CommandParameterSpec(parameter)
            for parameter in inspect.signature(func).parameters.values()
            if parameter.annotation not in {ElroyConfig, TurnContext}
        )
        specs.append(
            ToolCommandSpec(
                name=func.__name__,
                description=_first_doc_line(func),
                func=func,
                parameters=params,
                result_target=_result_target_for(func),
            )
        )
    return specs


def execute_tool_command(spec: ToolCommandSpec, ctx: ElroyConfig, session: ElroySession, values: dict[str, str]) -> Any:
    try:
        kwargs: dict[str, Any] = {}
        for parameter in spec.parameters:
            raw_value = values.get(parameter.name)
            casted_value = get_casted_value(parameter.parameter, raw_value or "")
            if casted_value is None and not parameter.is_optional:
                raise RecoverableToolError(f"Missing required value for '{parameter.name}'")
            if casted_value is not None:
                kwargs[parameter.name] = casted_value
        return invoke_with_session(spec.func, ctx, session, **kwargs)
    except RecoverableToolError:
        raise
    except Exception as exc:
        raise RecoverableToolError(str(exc)) from exc


def parse_slash_command(text: str) -> tuple[str, list[str]]:
    try:
        parts = shlex.split(text.removeprefix("/"))
    except ValueError:
        parts = text.removeprefix("/").split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


def build_initial_values(spec: ToolCommandSpec, values: list[str]) -> dict[str, str]:
    initial_values: dict[str, str] = {}
    for parameter, raw in zip(spec.parameters, values, strict=False):
        initial_values[parameter.name] = raw
    return initial_values


def can_execute_from_values(spec: ToolCommandSpec, values: list[str]) -> bool:
    return len(values) >= spec.required_parameter_count and len(values) <= len(spec.parameters)


class ToolCommandProvider(Provider):
    """Searchable command provider for repository and user commands."""

    @property
    def elroy_app(self) -> ElroyApp:
        return self.app  # type: ignore[return-value]

    async def discover(self) -> Hits:
        for spec in self.elroy_app.tool_command_specs:
            yield DiscoveryHit(
                display=f"/{spec.name}",
                command=lambda spec_name=spec.name: self.elroy_app.launch_tool_command(spec_name),
                help=spec.description,
            )

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for spec in self.elroy_app.tool_command_specs:
            command_text = f"/{spec.name}"
            haystack = f"{command_text} {spec.description}"
            if (match := matcher.match(haystack)) > 0:
                yield Hit(
                    match,
                    matcher.highlight(command_text),
                    lambda spec_name=spec.name: self.elroy_app.launch_tool_command(spec_name),
                    text=command_text,
                    help=spec.description,
                )
