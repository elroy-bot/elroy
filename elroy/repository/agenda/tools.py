"""Tools for managing daily agenda items."""

from datetime import date
from pathlib import Path

from rich.table import Table

from ...config.paths import get_agenda_dir
from ...core.constants import RecoverableToolError, tool, user_only_tool
from ...core.ctx import ElroyContext
from .file_storage import (
    list_agenda_items,
    mark_completed,
    read_item_text,
    write_agenda_item,
)


def _agenda_dir() -> Path:
    return get_agenda_dir()


@tool
def add_agenda_item(ctx: ElroyContext, text: str, item_date: str | None = None) -> str:
    """Add a new agenda item for a given date (defaults to today).

    Args:
        text (str): The agenda item text.
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        str: Confirmation message.
    """
    if item_date:
        try:
            target_date = date.fromisoformat(item_date)
        except ValueError:
            raise RecoverableToolError(f"Invalid date format '{item_date}'. Use YYYY-MM-DD.")
    else:
        target_date = date.today()

    agenda_dir = _agenda_dir()
    # Use the first line of text as the file name base
    name = text.split("\n")[0][:60]
    path = write_agenda_item(agenda_dir, name, text, target_date)
    return f"Agenda item added for {target_date.isoformat()}: {path.stem}"


@tool
def complete_agenda_item(ctx: ElroyContext, item_name: str) -> str:
    """Mark an agenda item as completed.

    Args:
        item_name (str): The file stem (name without .md) of the agenda item, or a substring of it.

    Returns:
        str: Confirmation message.
    """
    agenda_dir = _agenda_dir()
    matches = [p for p in agenda_dir.glob("*.md") if item_name.lower() in p.stem.lower()]
    if not matches:
        raise RecoverableToolError(f"No agenda item found matching '{item_name}'.")
    if len(matches) > 1:
        names = ", ".join(p.stem for p in matches)
        raise RecoverableToolError(f"Multiple agenda items match '{item_name}': {names}. Be more specific.")
    mark_completed(matches[0])
    return f"Agenda item '{matches[0].stem}' marked as completed."


@tool
def delete_agenda_item(ctx: ElroyContext, item_name: str) -> str:
    """Delete an agenda item permanently.

    Args:
        item_name (str): The file stem (name without .md) of the agenda item, or a substring of it.

    Returns:
        str: Confirmation message.
    """
    agenda_dir = _agenda_dir()
    matches = [p for p in agenda_dir.glob("*.md") if item_name.lower() in p.stem.lower()]
    if not matches:
        raise RecoverableToolError(f"No agenda item found matching '{item_name}'.")
    if len(matches) > 1:
        names = ", ".join(p.stem for p in matches)
        raise RecoverableToolError(f"Multiple agenda items match '{item_name}': {names}. Be more specific.")
    matches[0].unlink()
    return f"Agenda item '{matches[0].stem}' deleted."


@user_only_tool
def list_agenda_items_cmd(ctx: ElroyContext, item_date: str | None = None) -> Table | str:
    """List agenda items for a given date (defaults to today).

    Args:
        item_date (str | None): ISO 8601 date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Table: A formatted table of agenda items.
    """
    if item_date:
        try:
            target_date = date.fromisoformat(item_date)
        except ValueError:
            raise RecoverableToolError(f"Invalid date format '{item_date}'. Use YYYY-MM-DD.")
    else:
        target_date = date.today()

    agenda_dir = _agenda_dir()
    items = list_agenda_items(agenda_dir, for_date=target_date)

    if not items:
        return f"No agenda items for {target_date.isoformat()}."

    table = Table(title=f"Agenda for {target_date.isoformat()}", show_lines=True)
    table.add_column("Item", style="cyan")
    table.add_column("Text", style="green")

    for path, _fm, text in items:
        table.add_row(path.stem, text)

    return table


def get_today_agenda_titles() -> list[str]:
    """Return a list of today's incomplete agenda item names (for the UI panel)."""
    agenda_dir = _agenda_dir()
    items = list_agenda_items(agenda_dir, for_date=date.today())
    return [path.stem.replace("_", " ") for path, _fm, _text in items]
