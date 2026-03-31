# UI

This document describes the intended keyboard behavior of Elroy's terminal UI as implemented in the current Textual app.

## Interaction Model

Elroy has two main keyboard modes:

- Chat mode: the input box is focused and typing goes to the prompt.
- Command mode: one of three panes is focused for navigation:
  - conversation history
  - sidebar showing memories
  - sidebar showing agenda

Press `Escape` to toggle between chat mode and command mode.

The right panel shows a single list at a time. Its header always shows both `Memories` and `Agenda`, and the active section is highlighted.

## Global Keys

| Key | Expected behavior |
| --- | --- |
| `Ctrl+D` | Exit the app. |
| `Ctrl+C` | Cancel the current streaming response, if one is in progress. |
| `F2` | Toggle the right-hand panel open or closed. |
| `Escape` | Toggle between chat mode and command mode. |

## Chat Mode

When the input is focused:

| Key | Expected behavior |
| --- | --- |
| `Enter` | Submit the current prompt. |
| `Up` | Load the previous prompt from input history. |
| `Down` | Move forward through input history; eventually restore an empty prompt. |
| `Tab` | Accept slash-command completion. It should not move focus to another widget. |

Notes:

- Normal typing should stay in the input.
- After a response finishes or is cancelled, focus should return to the input.

## Command Mode

Command mode means one of these panes is focused:

- conversation history
- sidebar in `Memories` mode
- sidebar in `Agenda` mode

Agenda items that are currently due should appear in the agenda list with ` (Due)` appended to the title.

When a command-mode pane is focused:

| Key | Expected behavior |
| --- | --- |
| `j` | Move down in the active pane. For conversation history, scroll down. |
| `k` | Move up in the active pane. For conversation history, scroll up. |
| `Up` | Move up in the active pane. For conversation history, scroll up. |
| `Down` | Move down in the active pane. For conversation history, scroll down. |
| `Tab` | Toggle between conversation history and the sidebar. |
| `Shift+Tab` | Toggle between conversation history and the sidebar in reverse. |
| `m` | Show the sidebar in `Memories` mode and make it the active command-mode pane. |
| `g` | Show the sidebar in `Agenda` mode and make it the active command-mode pane. |
| `Enter` | Open the selected item when a sidebar pane is active. |
| `i` | Return focus to chat input. |
| `a` | Return focus to chat input. |
| `Escape` | Return focus to chat input. |

Notes:

- `i` and `a` are vim-style shortcuts for leaving command mode and going back to input.
- `m` and `g` are the primary way to switch the sidebar between memories and agenda.

## Detail Modal

Pressing `Enter` on a selected list item should open a detail modal.

In the detail modal:

| Key | Expected behavior |
| --- | --- |
| `Escape` | Close the modal. |
| `Enter` | Close the modal. |
| `q` | Close the modal. |
| `d` | For deletable items, start delete confirmation; pressing `d` again confirms deletion. Any other key cancels the confirmation state. |

Current deletable items:

- Memories
- Agenda items with due-item triggers

Plain agenda items without due-item triggers are view-only in the current UI.

## Hints Bar

The footer hints should reflect the current mode:

- In chat mode: show the keys for entering command mode, toggling the panel, and exiting.
- In command mode: show pane cycling, movement, open, and return-to-chat keys.

## Focus Rules

Focus should not silently land on internal widgets.

If focus escapes unexpectedly, the next keypress should recover by returning focus to the chat input.
