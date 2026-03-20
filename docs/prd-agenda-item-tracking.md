# PRD: Agenda Item Tracking — Checklist Items & Text Updates

**Status**: Draft
**Date**: 2026-03-20
**Branch**: `claude/agenda-item-tracking-prd-Od5k0`

---

## Overview

Elroy already has basic agenda item support (add, complete, delete, list). This PRD covers the next phase: **structured checklist items within an agenda item**, and **append-only text updates** so users can log progress over time.

---

## Goals

1. An agenda item can contain an ordered list of checklist sub-items, each with its own completion state.
2. Users (and the assistant) can update individual checklist items independently.
3. Users can append timestamped text notes to any agenda item over time.
4. The existing plain-text agenda item flow remains fully supported — checklist and notes are additive.

---

## Non-Goals

- No database migration — checklist and notes data stays in the existing markdown / YAML-frontmatter file format.
- No nested checklists (one level only).
- No due-dates or owners on individual checklist items.
- No full-text search across agenda items (that is a separate feature).

---

## Data Model

All data remains in `~/.elroy/agenda/<slug>.md` markdown files with YAML frontmatter.

### Frontmatter fields (extended)

| Field | Type | Description |
|---|---|---|
| `date` | `YYYY-MM-DD` | Date the item belongs to (required) |
| `completed` | `bool` | True when the whole agenda item is done |
| `checklist` | `list[dict]` | Optional ordered list of checklist entries |

Each `checklist` entry:

```yaml
checklist:
  - id: 1
    text: "Draft outline"
    completed: false
  - id: 2
    text: "Write first section"
    completed: true
```

### Body (text section)

The markdown body below the frontmatter fence continues to hold the main item description **plus** an optional **Updates** section appended by the tool.

```markdown
---
date: 2026-03-20
completed: false
checklist:
  - id: 1
    text: Draft outline
    completed: false
---

Write the Q2 report.

## Updates

- **2026-03-20 09:14**: Started outline, will revisit after standup.
- **2026-03-20 14:02**: First section done, two sections remaining.
```

The `## Updates` header is inserted automatically on first `add_agenda_item_update` call and all subsequent entries are appended under it.

---

## New Tools

### `add_agenda_item_checklist_item`

Add a new checklist entry to an existing agenda item.

```
add_agenda_item_checklist_item(ctx, item_name, checklist_text) -> str
```

- `item_name`: substring match against file stems (same logic as `complete_agenda_item`)
- `checklist_text`: description of the sub-task
- Appends to `checklist` list in frontmatter; auto-assigns next integer `id`
- Returns confirmation with the assigned id

### `complete_agenda_item_checklist_item`

Mark a single checklist entry as completed.

```
complete_agenda_item_checklist_item(ctx, item_name, checklist_id) -> str
```

- `item_name`: substring match against file stems
- `checklist_id`: integer id of the checklist entry
- Sets `completed: true` on that entry; does **not** auto-complete the parent item
- Returns confirmation

### `update_agenda_item_checklist_item`

Edit the text of an existing checklist entry.

```
update_agenda_item_checklist_item(ctx, item_name, checklist_id, new_text) -> str
```

- Updates `text` field on the matching checklist entry
- Returns confirmation

### `add_agenda_item_update`

Append a timestamped text note to an agenda item.

```
add_agenda_item_update(ctx, item_name, update_text) -> str
```

- `item_name`: substring match against file stems
- `update_text`: free-form note
- Inserts `## Updates` section if not present, then appends a bullet: `- **<ISO datetime>**: <update_text>`
- Returns confirmation with the timestamp used

---

## Changes to Existing Tools

### `list_agenda_items_cmd`

The table should show checklist progress when present:

| Item | Text | Checklist |
|---|---|---|
| write-q2-report | Write the Q2 report. | 1/3 done |

Add a `Checklist` column that shows `<completed>/<total> done` when the item has checklist entries, empty otherwise.

### `complete_agenda_item`

No change in behavior. Completing the parent item does not forcibly complete all checklist items — the file is marked `completed: true` and hidden from listings as today. Open checklist items are simply carried in the file as historical record.

---

## File Storage Changes (`file_storage.py`)

Add helpers:

- `read_checklist(path) -> list[dict]` — returns the `checklist` list from frontmatter (empty list if absent)
- `append_checklist_item(path, text) -> int` — appends entry, returns new id
- `set_checklist_item_completed(path, checklist_id, completed=True) -> None`
- `update_checklist_item_text(path, checklist_id, new_text) -> None`
- `append_update(path, update_text, timestamp=None) -> str` — appends to `## Updates` section, returns formatted timestamp

All checklist mutations use `update_frontmatter_fields` for frontmatter writes (existing utility). The `append_update` helper performs a raw file append after the frontmatter body.

---

## Tool Registration

New tools go in `tools_and_commands.py` under `ASSISTANT_VISIBLE_COMMANDS`:

- `add_agenda_item_checklist_item`
- `complete_agenda_item_checklist_item`
- `update_agenda_item_checklist_item`
- `add_agenda_item_update`

---

## Tests

| Test | What it checks |
|---|---|
| `test_add_checklist_item` | Adds two items, verifies frontmatter ids |
| `test_complete_checklist_item` | Marks one item completed, other unchanged |
| `test_update_checklist_item_text` | Edits text of entry |
| `test_add_agenda_item_update` | First call inserts `## Updates` header; second appends |
| `test_list_shows_checklist_progress` | Table `Checklist` column shows correct fraction |
| `test_complete_parent_does_not_force_checklist` | Parent completed, checklist entries keep their state |
| `test_substring_match_ambiguity` | Multiple matches raise `RecoverableToolError` |

Tests follow the existing pattern in `tests/` using pytest fixtures for a temporary agenda directory.

---

## Acceptance Criteria

1. `add_agenda_item_checklist_item("report", "Draft outline")` succeeds and the markdown file contains a `checklist` entry with `id: 1`.
2. `complete_agenda_item_checklist_item("report", 1)` sets that entry to `completed: true`.
3. `add_agenda_item_update("report", "Finished the draft")` appends a timestamped bullet under `## Updates`.
4. `list_agenda_items_cmd` shows checklist progress (`1/3 done`) for items with a checklist.
5. All new tools are accessible as slash commands.
6. All existing agenda item tests continue to pass.
7. An agenda item without a checklist continues to work exactly as before.
