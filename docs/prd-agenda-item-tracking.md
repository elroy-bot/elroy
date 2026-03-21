# PRD: Agenda Item Tracking — Checklist Items & Text Updates

**Status**: Draft
**Date**: 2026-03-20

---

## Overview

This PRD covers **structured checklist items within an agenda item**, and **append-only text updates** so users can log progress over time.

---

## Goals

1. An agenda item can contain an ordered list of checklist sub-items, each with its own completion state.
2. Users (and the assistant) can update individual checklist items independently.
3. Users can append timestamped text notes to any agenda item over time.
4. The plain-text agenda item flow remains fully supported — checklist and notes are additive.

---

## Non-Goals

- No database migration — checklist and notes data uses the markdown / YAML-frontmatter file format.
- No nested checklists (one level only).
- No owners on individual checklist items.
- No full-text search across agenda items (that is a separate feature).

---

## Data Model

All recallable information is stored in markdown files with YAML frontmatter, within elroy's configurable home directory.

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
    due_date: "2026-03-25"
  - id: 2
    text: "Write first section"
    completed: true
```

`due_date` is optional (`YYYY-MM-DD`).

### Body (text section)

The markdown body below the frontmatter fence holds the main item description plus an optional **Updates** section appended over time.

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

The Updates section is created automatically on the first update and all subsequent entries are appended under it.

---

## New Capabilities

### Add checklist item

Add a sub-task to an agenda item. The item is identified by partial name match. The sub-task is appended to the checklist with a unique sequential id and an optional due date. Returns confirmation with the assigned id.

### Complete checklist item

Mark a single checklist sub-task as done. Does not auto-complete the parent agenda item.

### Edit checklist item

Update the text of a checklist sub-task.

### Add agenda item update

Append a timestamped note to an agenda item. Creates an Updates section in the item if one does not yet exist. Returns confirmation with the timestamp used.

---

## Changes to Existing Behavior

### Agenda item listing

Add a checklist progress column showing `<completed>/<total> done` for items that have checklist entries, empty otherwise. Example:

| Item | Text | Checklist |
|---|---|---|
| write-q2-report | Write the Q2 report. | 1/3 done |

### Completing an agenda item

No change in behavior. Completing the parent item does not forcibly complete checklist sub-tasks. Open sub-tasks are carried in the file as historical record.

---

## Tests

- Adding two checklist sub-tasks produces entries with sequential ids
- Completing one sub-task does not affect others
- Editing a sub-task's text is reflected in the stored item
- First update creates an Updates section; subsequent updates append to it
- The agenda item listing shows checklist progress as a fraction
- Completing the parent item leaves sub-task completion states unchanged
- Ambiguous partial name matches produce a clear error to the user

---

## Acceptance Criteria

1. Adding a checklist sub-task to an agenda item stores it with a sequential id.
2. Completing a checklist sub-task marks only that entry done, not the parent.
3. Appending an update adds a timestamped bullet under an Updates section, creating it if absent.
4. The agenda item listing shows checklist progress (e.g. "1/3 done") for items with sub-tasks.
5. All new capabilities are accessible as slash commands.
6. All agenda item tests continue to pass.
7. An agenda item without a checklist works exactly as before.
