"""Reusable Textual modal forms for TUI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.validation import Function
from textual.widgets import Button, Input, Label

from .textual_commands import ToolCommandSpec

if TYPE_CHECKING:
    from .textual_app import ElroyApp


class CommandFormScreen(ModalScreen[dict[str, str] | None]):
    """Collect arguments for a tool command with widget-native validation."""

    DEFAULT_CSS = """
    CommandFormScreen {
        align: center middle;
    }
    #command-form-container {
        width: 72;
        max-height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    .command-form-title {
        margin-bottom: 1;
        color: $text;
        text-style: bold;
    }
    .command-form-help {
        margin-bottom: 1;
        color: $text-muted;
    }
    .command-form-field {
        margin: 0 0 1 0;
    }
    .command-form-error {
        color: $error;
        margin-bottom: 1;
        min-height: 1;
    }
    #command-form-actions {
        height: auto;
        align-horizontal: right;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, spec: ToolCommandSpec, initial_values: dict[str, str] | None = None):
        super().__init__()
        self.spec = spec
        self.initial_values = initial_values or {}

    @property
    def elroy_app(self) -> ElroyApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        with Vertical(id="command-form-container"):
            yield Label(f"/{self.spec.name}", classes="command-form-title")
            yield Label(self.spec.description, classes="command-form-help")
            for parameter in self.spec.parameters:
                yield Label(parameter.name.replace("_", " ").title())
                validators = []
                if not parameter.is_optional:
                    validators.append(Function(lambda value: bool(value.strip()), "This field is required"))
                yield Input(
                    value=self.initial_values.get(parameter.name, parameter.default_text),
                    placeholder="" if not parameter.is_optional else "Optional",
                    validators=validators or None,
                    validate_on=["submitted", "changed"],
                    suggester=self.spec.build_suggester(self.elroy_app, parameter.name),
                    id=f"input-{parameter.name}",
                    classes="command-form-field",
                )
            yield Label("", id="command-form-error", classes="command-form-error")
            with Horizontal(id="command-form-actions"):
                yield Button("Cancel", id="command-form-cancel")
                yield Button("Run", variant="primary", id="command-form-submit")

    def on_mount(self) -> None:
        first_input = self.query("Input").first()
        if first_input is not None:
            first_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "command-form-cancel":
            self.dismiss(None)
            return
        if event.button.id == "command-form-submit":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.validation_result is not None and not event.validation_result.is_valid:
            self._render_error(event.validation_result.failure_descriptions[0])
            return
        self._submit()

    def _submit(self) -> None:
        values: dict[str, str] = {}
        for parameter in self.spec.parameters:
            widget = self.query_one(f"#input-{parameter.name}", Input)
            validation_result = widget.validate(widget.value)
            if validation_result is not None and not validation_result.is_valid:
                self._render_error(validation_result.failure_descriptions[0])
                widget.focus()
                return
            values[parameter.name] = widget.value.strip()
        self.dismiss(values)

    def _render_error(self, message: str) -> None:
        self.query_one("#command-form-error", Label).update(message)
