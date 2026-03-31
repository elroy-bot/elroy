# UI

This document describes the intended keyboard behavior of Elroy's terminal UI as implemented in the current Textual app.

## Interaction Model

Elroy has two main keyboard modes:

- Chat mode: the input box is focused and typing goes to the prompt.
- Browse mode: the right-hand panel list is focused and keys navigate memories, reminders, or agenda items.

Press `Escape` to toggle between chat mode and browse mode.

If the right panel is hidden when you enter browse mode, Elroy should show it automatically and focus the current list.

## Global Keys

| Key | Expected behavior |
| --- | --- |
| `Ctrl+D` | Exit the app. |
| `Ctrl+C` | Cancel the current streaming response, if one is in progress. |
| `F2` | Toggle the right-hand panel open or closed. |
| `Escape` | Toggle between chat mode and browse mode. |

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

## Browse Mode

Browse mode means the right-panel list is focused.

The right panel has three buffers:

- Memories
- Reminders
- Agenda

When the browse list is focused:

| Key | Expected behavior |
| --- | --- |
| `j` | Move selection down. |
| `k` | Move selection up. |
| `Up` | Move selection up. |
| `Down` | Move selection down. |
| `Tab` | Cycle to the next buffer: Memories -> Reminders -> Agenda -> Memories. |
| `Shift+Tab` | Cycle to the previous buffer. |
| `Enter` | Open the selected item. |
| `i` | Return focus to chat input. |
| `a` | Return focus to chat input. |
| `Escape` | Return focus to chat input. |

Notes:

- `i` and `a` are vim-style shortcuts for leaving browse mode and going back to input.
- Switching buffers should preserve browse mode and keep focus on the list.

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
- Reminders

Agenda items are view-only in the current UI.

## Hints Bar

The footer hints should reflect the current mode:

- In chat mode: show the keys for browsing, toggling the panel, and exiting.
- In browse mode: show movement keys, buffer cycling, open, and return-to-chat keys.

## Focus Rules

Focus should not silently land on internal widgets like tabs or the conversation log.

If focus escapes unexpectedly, the next keypress should recover by returning focus to the chat input.
