from typing import Any, cast

from rich.console import Console

from elroy.db.db_models import FunctionCall
from elroy.llm.stream_parser import AssistantToolResult
from elroy.repository.data_models import AgendaListItem, AgendaListResponse
from elroy.ui.output import TextualIO


class _StubApp:
    def __init__(self) -> None:
        self.writes: list[object] = []

    def call_from_thread(self, fn, *args) -> None:
        fn(*args)

    def _append_thought_token(self, token: str) -> None:
        del token

    def _flush_thought_buffer(self) -> None:
        return

    def _append_streaming_token(self, token: str, style: str) -> None:
        del token, style

    def _write_to_history(self, renderable) -> None:
        self.writes.append(renderable)


def _render_to_text(renderable) -> str:
    console = Console(force_terminal=False, no_color=True, width=100)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


def test_rich_formatter_renders_function_call_as_panel(rich_formatter) -> None:
    function_call = FunctionCall(
        id="call-1",
        function_name="add_agenda_item",
        arguments={"text": "Call with Protege", "item_date": "2026-04-28"},
    )

    renderables = list(rich_formatter.format(function_call))

    assert len(renderables) == 1

    rendered = _render_to_text(renderables[0])
    assert "Tool Call" in rendered
    assert "add_agenda_item" in rendered
    assert "text" in rendered
    assert "Call with Protege" in rendered
    assert "item_date" in rendered
    assert "2026-04-28" in rendered
    assert "{" not in rendered


def test_rich_formatter_renders_json_tool_results_as_panel(rich_formatter) -> None:
    tool_result = AssistantToolResult(content='{"status":"ok","count":2}', is_error=False)

    renderables = list(rich_formatter.format(tool_result))

    assert len(renderables) == 1

    rendered = _render_to_text(renderables[0])
    assert "Tool Result" in rendered
    assert "status" in rendered
    assert "ok" in rendered
    assert "count" in rendered
    assert "2" in rendered


def test_rich_formatter_renders_agenda_results_as_table(rich_formatter) -> None:
    tool_result = AgendaListResponse(
        item_date="2026-04-28",
        items=[
            AgendaListItem(
                name="Call_with_Protege",
                text="Call with Protege",
                checklist_completed=1,
                checklist_total=3,
            )
        ],
    )

    renderables = list(rich_formatter.format(tool_result))

    assert len(renderables) == 1

    rendered = _render_to_text(renderables[0])
    assert "Agenda for 2026-04-28" in rendered
    assert "Item" in rendered
    assert "Text" in rendered
    assert "Checklist" in rendered
    assert "Call_with_Protege" in rendered
    assert "Call with Protege" in rendered
    assert "1/3 done" in rendered


def test_textual_io_truncates_large_tool_results_before_rendering(rich_formatter) -> None:
    app = _StubApp()
    io = TextualIO(app=cast(Any, app), formatter=rich_formatter, show_internal_thought=False)

    io.print(AssistantToolResult(content="x" * 501, is_error=False))

    assert len(app.writes) == 1

    rendered = _render_to_text(app.writes[0])
    assert "Tool Result" in rendered
    assert "< 501 char tool result >" in rendered
