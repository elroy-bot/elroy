"""Command flow controller for the Textual app."""

from __future__ import annotations

from dataclasses import dataclass

from .commands import (
    ToolCommandSpec,
    build_initial_values,
    build_tool_command_specs,
    can_execute_from_values,
    parse_slash_command,
)


@dataclass(frozen=True)
class CommandLaunchRequest:
    """Resolved request for a command launch or execution."""

    spec: ToolCommandSpec
    initial_values: dict[str, str]
    source: str
    execute_immediately: bool


class CommandFlowController:
    """Owns command-spec lookup and launch/execute decision logic."""

    def __init__(self, ctx):
        self.tool_command_specs = build_tool_command_specs(ctx)

    def get_tool_command_spec(self, name: str) -> ToolCommandSpec | None:
        return next((spec for spec in self.tool_command_specs if spec.name == name), None)

    def resolve_launch_request(
        self, name: str, initial_values: dict[str, str] | None = None, source: str = "palette"
    ) -> CommandLaunchRequest | None:
        spec = self.get_tool_command_spec(name)
        if spec is None:
            return None
        resolved_values = initial_values or {}
        return CommandLaunchRequest(
            spec=spec,
            initial_values=resolved_values,
            source=source,
            execute_immediately=spec.is_zero_arg and not resolved_values,
        )

    def resolve_slash_command(self, text: str) -> tuple[CommandLaunchRequest | None, str | None]:
        command_name, raw_values = parse_slash_command(text)
        if not command_name:
            return None, None
        spec = self.get_tool_command_spec(command_name)
        if spec is None:
            return None, command_name
        initial_values = build_initial_values(spec, raw_values)
        return (
            CommandLaunchRequest(
                spec=spec,
                initial_values=initial_values,
                source="slash",
                execute_immediately=spec.is_zero_arg or can_execute_from_values(spec, raw_values),
            ),
            None,
        )
