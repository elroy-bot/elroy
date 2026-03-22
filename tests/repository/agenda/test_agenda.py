from datetime import date, datetime

import pytest
from rich.console import Console

from elroy.config.paths import get_agenda_dir
from elroy.core.constants import RecoverableToolError
from elroy.core.ctx import ElroyContext
from elroy.messenger.slash_commands import invoke_slash_command
from elroy.repository.agenda.file_storage import (
    append_agenda_update,
    find_matching_agenda_item,
    get_checklist,
    write_agenda_item,
)
from elroy.repository.agenda.tools import (
    add_agenda_checklist_item,
    add_agenda_item,
    add_agenda_item_update,
    complete_agenda_checklist_item,
    complete_agenda_item,
    edit_agenda_checklist_item,
    list_agenda_items_cmd,
)
from elroy.repository.file_utils import read_file_text, read_frontmatter
from tests.utils import MockCliIO


@pytest.fixture
def agenda_dir(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    return get_agenda_dir()


def _render_table(table) -> str:
    console = Console(force_terminal=False, width=120, color_system=None, record=True)
    console.print(table)
    return console.export_text()


def test_adding_checklist_items_assigns_sequential_ids(agenda_dir):
    path = write_agenda_item(agenda_dir, "Write Q2 report", "Write the Q2 report.", date(2026, 3, 20))

    first_id = add_agenda_checklist_item(None, path.stem, "Draft outline", "2026-03-25")
    second_id = add_agenda_checklist_item(None, path.stem, "Write first section")

    checklist = get_checklist(path)
    assert "Checklist item 1" in first_id
    assert "Checklist item 2" in second_id
    assert checklist == [
        {"id": 1, "text": "Draft outline", "completed": False, "due_date": "2026-03-25"},
        {"id": 2, "text": "Write first section", "completed": False},
    ]


def test_complete_one_checklist_item_does_not_affect_others(agenda_dir):
    path = write_agenda_item(agenda_dir, "Write Q2 report", "Write the Q2 report.", date(2026, 3, 20))
    add_agenda_checklist_item(None, path.stem, "Draft outline")
    add_agenda_checklist_item(None, path.stem, "Write first section")

    complete_agenda_checklist_item(None, path.stem, 1)

    checklist = get_checklist(path)
    assert checklist[0]["completed"] is True
    assert checklist[1]["completed"] is False


def test_edit_checklist_item_updates_stored_text(agenda_dir):
    path = write_agenda_item(agenda_dir, "Write Q2 report", "Write the Q2 report.", date(2026, 3, 20))
    add_agenda_checklist_item(None, path.stem, "Draft")

    edit_agenda_checklist_item(None, path.stem, 1, "Draft outline")

    assert get_checklist(path)[0]["text"] == "Draft outline"


def test_first_update_creates_updates_section_and_later_updates_append(agenda_dir):
    path = write_agenda_item(agenda_dir, "Write Q2 report", "Write the Q2 report.", date(2026, 3, 20))

    first_ts = append_agenda_update(path, "Started outline", datetime(2026, 3, 20, 9, 14))
    second_ts = append_agenda_update(path, "First section done", datetime(2026, 3, 20, 14, 2))

    body = read_file_text(path)
    assert first_ts == "2026-03-20 09:14"
    assert second_ts == "2026-03-20 14:02"
    assert "## Updates" in body
    assert "- **2026-03-20 09:14**: Started outline" in body
    assert "- **2026-03-20 14:02**: First section done" in body
    assert body.index("Started outline") < body.index("First section done")


def test_listing_shows_checklist_progress_fraction(agenda_dir):
    path = write_agenda_item(agenda_dir, "Write Q2 report", "Write the Q2 report.", date(2026, 3, 20))
    add_agenda_checklist_item(None, path.stem, "Draft outline")
    add_agenda_checklist_item(None, path.stem, "Write first section")
    complete_agenda_checklist_item(None, path.stem, 1)

    table = list_agenda_items_cmd(None, "2026-03-20")
    rendered = _render_table(table)

    assert "Checklist" in rendered
    assert "1/2 done" in rendered
    assert "Write the Q2 report." in rendered


def test_completing_parent_item_preserves_subtask_state(agenda_dir):
    path = write_agenda_item(agenda_dir, "Write Q2 report", "Write the Q2 report.", date(2026, 3, 20))
    add_agenda_checklist_item(None, path.stem, "Draft outline")
    add_agenda_checklist_item(None, path.stem, "Write first section")
    complete_agenda_checklist_item(None, path.stem, 1)

    complete_agenda_item(None, path.stem)

    frontmatter = read_frontmatter(path)
    assert frontmatter["completed"] is True
    assert get_checklist(path)[0]["completed"] is True
    assert get_checklist(path)[1]["completed"] is False


def test_ambiguous_partial_name_matches_raise_clear_error(agenda_dir):
    write_agenda_item(agenda_dir, "Write Q2 report", "Write the Q2 report.", date(2026, 3, 20))
    write_agenda_item(agenda_dir, "Write Q3 report", "Write the Q3 report.", date(2026, 3, 20))

    with pytest.raises(ValueError, match="Multiple agenda items match 'write'"):
        find_matching_agenda_item(agenda_dir, "write")

    with pytest.raises(RecoverableToolError, match="Multiple agenda items match 'write'"):
        add_agenda_item_update(None, "write", "Blocked")


def test_new_agenda_capabilities_are_registered_as_slash_commands(ctx: ElroyContext, agenda_dir, io: MockCliIO):
    add_agenda_item(ctx, "Write the Q2 report.", "2026-03-20")

    for command in [
        "add_agenda_checklist_item",
        "complete_agenda_checklist_item",
        "edit_agenda_checklist_item",
        "add_agenda_item_update",
    ]:
        assert command in ctx.tool_registry.tools

    io._user_responses = ["Write_the_Q2_report", "Draft outline", "2026-03-25"]
    result = invoke_slash_command(io, ctx, "/add_agenda_checklist_item")

    assert result == "Checklist item 1 added to 'Write_the_Q2_report'."
