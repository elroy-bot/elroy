"""Tools for managing daily agenda items."""

from datetime import date
from pathlib import Path

from rich.table import Table

from ...config.paths import get_agenda_dir
from ...core.constants import RecoverableToolError, tool, user_only_tool
from ...core.ctx import ElroyConfig
from ...core.session import build_elroy_session, open_turn_context
from ...core.turn import TurnContext
from ...repository.recall.factory import build_recall_indexer
from ..data_models import AgendaListItem, AgendaListResponse
from ..tasks.factory import build_task_mutation_orchestrator, build_task_store
from .file_storage import (
    add_checklist_item,
    append_agenda_update,
    find_matching_agenda_item,
    get_checklist,
    mark_completed,
    update_checklist_item,
    write_agenda_item,
)
from .file_storage import (
    list_agenda_items as list_agenda_items_from_dir,
)


def _parse_iso_date(item_date: str | None) -> date:
    if item_date:
        try:
            return date.fromisoformat(item_date)
        except ValueError as e:
            raise RecoverableToolError(f"Invalid date format '{item_date}'. Use YYYY-MM-DD.") from e
    return date.today()


def _parse_due_date(due_date: str | None) -> str | None:
    if due_date is None:
        return None
    try:
        return date.fromisoformat(due_date).isoformat()
    except ValueError as e:
        raise RecoverableToolError(f"Invalid due_date format '{due_date}'. Use YYYY-MM-DD.") from e


def _find_agenda_path(item_name: str):
    try:
        return find_matching_agenda_item(get_agenda_dir(), item_name)
    except FileNotFoundError as e:
        raise RecoverableToolError(str(e)) from e
    except ValueError as e:
        raise RecoverableToolError(str(e)) from e


def _build_agenda_list_response(target_date: date) -> AgendaListResponse:
    agenda_dir = get_agenda_dir()
    items = list_agenda_items_from_dir(agenda_dir, for_date=target_date)

    response_items: list[AgendaListItem] = []
    for path, _fm, text in items:
        main_text = text.split("\n## Updates\n", 1)[0].strip()
        checklist = get_checklist(path)
        completed_count = sum(1 for item in checklist if item["completed"])
        response_items.append(
            AgendaListItem(
                name=path.stem,
                text=main_text,
                checklist_completed=completed_count,
                checklist_total=len(checklist),
            )
        )

    return AgendaListResponse(item_date=target_date.isoformat(), items=response_items)


def _add_agenda_item_without_ctx(text: str, item_date: str | None = None) -> str:
    target_date = _parse_iso_date(item_date)
    name = text.split("\n")[0][:60]
    path = write_agenda_item(get_agenda_dir(), name, text, target_date)
    return f"Agenda item added for {target_date.isoformat()}: {path.stem}"


def do_add_agenda_item(turn: TurnContext, text: str, item_date: str | None = None) -> str:
    target_date = _parse_iso_date(item_date)
    name = text.split("\n")[0][:60]
    row = build_task_mutation_orchestrator(turn).create_task(name, text, item_date=target_date)
    return f"Agenda item added for {target_date.isoformat()}: {row.name}"


def _complete_agenda_item_without_ctx(item_name: str) -> str:
    path = _find_agenda_path(item_name)
    mark_completed(path)
    return f"Agenda item '{path.stem}' marked as completed."


def do_complete_agenda_item(turn: TurnContext, item_name: str) -> str:
    path = _find_agenda_path(item_name)
    mark_completed(path)
    row = build_task_store(turn).get_task_by_file_path(path)
    if row:
        build_task_mutation_orchestrator(turn).complete_task(row.name)
    return f"Agenda item '{path.stem}' marked as completed."


def _delete_agenda_item_without_ctx(item_name: str) -> str:
    path = _find_agenda_path(item_name)
    path.unlink()
    return f"Agenda item '{path.stem}' deleted."


def do_delete_agenda_item(turn: TurnContext, item_name: str) -> str:
    path = _find_agenda_path(item_name)
    row = build_task_store(turn).get_task_by_file_path(path)
    if row:
        build_task_mutation_orchestrator(turn).delete_task(row.name, delete_file=True)
    else:
        path.unlink()
    return f"Agenda item '{path.stem}' deleted."


def do_reembed_agenda_item(turn: TurnContext, path: Path) -> None:
    row = build_task_store(turn).get_task_by_file_path(path)
    if row:
        build_recall_indexer(turn).upsert_embedding_if_needed(row)


@tool
def add_agenda_item(ctx: ElroyConfig, text: str, item_date: str | None = None) -> str:
    """Add a new agenda item for a given date (defaults to today).

    Args:
        text (str): The agenda item text.
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        str: Confirmation message.
    """
    if ctx is None:
        return _add_agenda_item_without_ctx(text, item_date)
    with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
        return do_add_agenda_item(turn, text, item_date)


@tool
def complete_agenda_item(ctx: ElroyConfig, item_name: str) -> str:
    """Mark an agenda item as completed.

    Args:
        item_name (str): The file stem (name without .md) of the agenda item, or a substring of it.

    Returns:
        str: Confirmation message.
    """
    if ctx is None:
        return _complete_agenda_item_without_ctx(item_name)
    with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
        return do_complete_agenda_item(turn, item_name)


@tool
def delete_agenda_item(ctx: ElroyConfig, item_name: str) -> str:
    """Delete an agenda item permanently.

    Args:
        item_name (str): The file stem (name without .md) of the agenda item, or a substring of it.

    Returns:
        str: Confirmation message.
    """
    if ctx is None:
        return _delete_agenda_item_without_ctx(item_name)
    with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
        return do_delete_agenda_item(turn, item_name)


@tool
def add_agenda_checklist_item(
    ctx: ElroyConfig,
    item_name: str,
    text: str,
    due_date: str | None = None,
) -> str:
    """Add a checklist sub-task to an agenda item.

    Args:
        item_name (str): Agenda item stem or a unique substring match.
        text (str): Checklist item text.
        due_date (str | None): Optional ISO date string (YYYY-MM-DD).

    Returns:
        str: Confirmation with the assigned checklist id.
    """
    path = _find_agenda_path(item_name)
    checklist_id = add_checklist_item(path, text, _parse_due_date(due_date))
    if ctx is not None:
        with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
            do_reembed_agenda_item(turn, path)
    return f"Checklist item {checklist_id} added to '{path.stem}'."


@tool
def complete_agenda_checklist_item(ctx: ElroyConfig, item_name: str, checklist_item_id: int) -> str:
    """Mark a single checklist sub-task as completed.

    Args:
        item_name (str): Agenda item stem or a unique substring match.
        checklist_item_id (int): Checklist entry id to complete.

    Returns:
        str: Confirmation message.
    """
    path = _find_agenda_path(item_name)
    try:
        item = update_checklist_item(path, checklist_item_id, completed=True)
    except LookupError as e:
        raise RecoverableToolError(f"Agenda item '{path.stem}' has no checklist item {checklist_item_id}.") from e
    if ctx is not None:
        with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
            do_reembed_agenda_item(turn, path)
    return f"Checklist item {item['id']} on '{path.stem}' marked as completed."


@tool
def edit_agenda_checklist_item(ctx: ElroyConfig, item_name: str, checklist_item_id: int, new_text: str) -> str:
    """Update the text of an agenda checklist item.

    Args:
        item_name (str): Agenda item stem or a unique substring match.
        checklist_item_id (int): Checklist entry id to edit.
        new_text (str): Replacement text.

    Returns:
        str: Confirmation message.
    """
    path = _find_agenda_path(item_name)
    try:
        item = update_checklist_item(path, checklist_item_id, text=new_text)
    except LookupError as e:
        raise RecoverableToolError(f"Agenda item '{path.stem}' has no checklist item {checklist_item_id}.") from e
    if ctx is not None:
        with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
            do_reembed_agenda_item(turn, path)
    return f"Checklist item {item['id']} on '{path.stem}' updated."


@tool
def add_agenda_item_update(ctx: ElroyConfig, item_name: str, note: str) -> str:
    """Append a timestamped progress note to an agenda item.

    Args:
        item_name (str): Agenda item stem or a unique substring match.
        note (str): Update text to append.

    Returns:
        str: Confirmation with the timestamp used.
    """
    path = _find_agenda_path(item_name)
    used_timestamp = append_agenda_update(path, note)
    if ctx is not None:
        with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
            do_reembed_agenda_item(turn, path)
    return f"Update added to '{path.stem}' at {used_timestamp}."


@tool
def list_agenda_items(ctx: ElroyConfig, item_date: str | None = None) -> AgendaListResponse:
    """List agenda items for a given date (defaults to today).

    Args:
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        AgendaListResponse: Structured agenda items for the requested date.
    """
    _ = ctx
    target_date = _parse_iso_date(item_date)
    return _build_agenda_list_response(target_date)


@user_only_tool
def list_agenda_items_cmd(ctx: ElroyConfig, item_date: str | None = None) -> Table | str:
    """List agenda items for a given date (defaults to today).

    Args:
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Table: A formatted table of agenda items.
    """
    _ = ctx
    target_date = _parse_iso_date(item_date)
    response = _build_agenda_list_response(target_date)

    if not response.items:
        return f"No agenda items for {target_date.isoformat()}."

    table = Table(title=f"Agenda for {target_date.isoformat()}", show_lines=True)
    table.add_column("Item", style="cyan")
    table.add_column("Text", style="green")
    table.add_column("Checklist", style="magenta")

    for item in response.items:
        table.add_row(item.name, item.text, item.checklist_progress)

    return table


def get_today_agenda_titles() -> list[str]:
    """Return a list of today's incomplete agenda item names (for the UI panel)."""
    agenda_dir = get_agenda_dir()
    items = list_agenda_items_from_dir(agenda_dir, for_date=date.today())
    return [text.split("\n")[0] for _path, _fm, text in items]


def do_get_active_agenda_titles(turn: TurnContext) -> list[str]:
    return build_task_store(turn).get_active_agenda_titles()


def get_active_agenda_titles(ctx: ElroyConfig) -> list[str]:
    """Return active non-triggered agenda item names for command completion."""
    with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
        return do_get_active_agenda_titles(turn)
