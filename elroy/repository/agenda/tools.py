"""Tools for managing daily agenda items."""

from datetime import date

from rich.table import Table
from sqlmodel import col, select

from ...config.paths import get_agenda_dir
from ...core.constants import RecoverableToolError, tool, user_only_tool
from ...core.ctx import ElroyContext
from ...db.db_models import AgendaItem
from ...repository.recall.operations import upsert_embedding_if_needed
from ..tasks.operations import complete_task, create_task, delete_task
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


@tool
def add_agenda_item(ctx: ElroyContext, text: str, item_date: str | None = None) -> str:
    """Add a new agenda item for a given date (defaults to today).

    Args:
        text (str): The agenda item text.
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        str: Confirmation message.
    """
    target_date = _parse_iso_date(item_date)
    # Use the first line of text as the file name base
    name = text.split("\n")[0][:60]
    if ctx is None:
        path = write_agenda_item(get_agenda_dir(), name, text, target_date)
        return f"Agenda item added for {target_date.isoformat()}: {path.stem}"

    row = create_task(ctx, name, text, item_date=target_date)
    return f"Agenda item added for {target_date.isoformat()}: {row.name}"


@tool
def complete_agenda_item(ctx: ElroyContext, item_name: str) -> str:
    """Mark an agenda item as completed.

    Args:
        item_name (str): The file stem (name without .md) of the agenda item, or a substring of it.

    Returns:
        str: Confirmation message.
    """
    path = _find_agenda_path(item_name)
    mark_completed(path)
    if ctx is not None:
        row = ctx.db.exec(select(AgendaItem).where(AgendaItem.file_path == str(path), AgendaItem.user_id == ctx.user_id)).first()
        if row:
            complete_task(ctx, row.name)
    return f"Agenda item '{path.stem}' marked as completed."


@tool
def delete_agenda_item(ctx: ElroyContext, item_name: str) -> str:
    """Delete an agenda item permanently.

    Args:
        item_name (str): The file stem (name without .md) of the agenda item, or a substring of it.

    Returns:
        str: Confirmation message.
    """
    path = _find_agenda_path(item_name)
    if ctx is not None:
        row = ctx.db.exec(select(AgendaItem).where(AgendaItem.file_path == str(path), AgendaItem.user_id == ctx.user_id)).first()
        if row:
            delete_task(ctx, row.name, delete_file=True)
        else:
            path.unlink()
    else:
        path.unlink()
    return f"Agenda item '{path.stem}' deleted."


def _reembed_agenda_item(ctx: ElroyContext, path) -> None:
    if ctx is None:
        return
    row = ctx.db.exec(select(AgendaItem).where(AgendaItem.file_path == str(path), AgendaItem.user_id == ctx.user_id)).first()
    if row:
        upsert_embedding_if_needed(ctx, row)


@tool
def add_agenda_checklist_item(
    ctx: ElroyContext,
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
    _reembed_agenda_item(ctx, path)
    return f"Checklist item {checklist_id} added to '{path.stem}'."


@tool
def complete_agenda_checklist_item(ctx: ElroyContext, item_name: str, checklist_item_id: int) -> str:
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
    _reembed_agenda_item(ctx, path)
    return f"Checklist item {item['id']} on '{path.stem}' marked as completed."


@tool
def edit_agenda_checklist_item(ctx: ElroyContext, item_name: str, checklist_item_id: int, new_text: str) -> str:
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
    _reembed_agenda_item(ctx, path)
    return f"Checklist item {item['id']} on '{path.stem}' updated."


@tool
def add_agenda_item_update(ctx: ElroyContext, item_name: str, note: str) -> str:
    """Append a timestamped progress note to an agenda item.

    Args:
        item_name (str): Agenda item stem or a unique substring match.
        note (str): Update text to append.

    Returns:
        str: Confirmation with the timestamp used.
    """
    path = _find_agenda_path(item_name)
    used_timestamp = append_agenda_update(path, note)
    _reembed_agenda_item(ctx, path)
    return f"Update added to '{path.stem}' at {used_timestamp}."


@tool
def list_agenda_items(ctx: ElroyContext, item_date: str | None = None) -> str:
    """List agenda items for a given date (defaults to today).

    Args:
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        str: A text description of agenda items.
    """
    target_date = _parse_iso_date(item_date)
    agenda_dir = get_agenda_dir()
    items = list_agenda_items_from_dir(agenda_dir, for_date=target_date)

    if not items:
        return f"No agenda items for {target_date.isoformat()}."

    lines = [f"Agenda for {target_date.isoformat()}:"]
    for path, _fm, text in items:
        main_text = text.split("\n## Updates\n", 1)[0].strip()
        checklist = get_checklist(path)
        checklist_info = ""
        if checklist:
            completed_count = sum(1 for item in checklist if item["completed"])
            checklist_info = f" [{completed_count}/{len(checklist)} checklist items done]"
        lines.append(f"- {path.stem}: {main_text}{checklist_info}")
    return "\n".join(lines)


@user_only_tool
def list_agenda_items_cmd(ctx: ElroyContext, item_date: str | None = None) -> Table | str:
    """List agenda items for a given date (defaults to today).

    Args:
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Table: A formatted table of agenda items.
    """
    target_date = _parse_iso_date(item_date)

    agenda_dir = get_agenda_dir()
    items = list_agenda_items_from_dir(agenda_dir, for_date=target_date)

    if not items:
        return f"No agenda items for {target_date.isoformat()}."

    table = Table(title=f"Agenda for {target_date.isoformat()}", show_lines=True)
    table.add_column("Item", style="cyan")
    table.add_column("Text", style="green")
    table.add_column("Checklist", style="magenta")

    for path, _fm, text in items:
        main_text = text.split("\n## Updates\n", 1)[0].strip()
        checklist = get_checklist(path)
        checklist_progress = ""
        if checklist:
            completed_count = sum(1 for item in checklist if item["completed"])
            checklist_progress = f"{completed_count}/{len(checklist)} done"
        table.add_row(path.stem, main_text, checklist_progress)

    return table


def get_today_agenda_titles() -> list[str]:
    """Return a list of today's incomplete agenda item names (for the UI panel)."""
    agenda_dir = get_agenda_dir()
    items = list_agenda_items_from_dir(agenda_dir, for_date=date.today())
    return [text.split("\n")[0] for _path, _fm, text in items]


def get_active_agenda_titles(ctx: ElroyContext) -> list[str]:
    """Return active non-triggered agenda item names for command completion."""
    return sorted(
        [
            item.name
            for item in ctx.db.exec(
                select(AgendaItem).where(
                    AgendaItem.user_id == ctx.user_id,
                    col(AgendaItem.is_active).is_(True),
                    col(AgendaItem.trigger_datetime).is_(None),
                    col(AgendaItem.trigger_context).is_(None),
                )
            ).all()
        ]
    )
