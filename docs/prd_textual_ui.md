# PRD: Textual-based CLI UI

## Overview

Replace the current Rich/prompt_toolkit CLI with a Textual TUI application. The new interface is a persistent, panel-based layout with streaming AI output, dismissible context panels, and a system status footer.

---

## Layout

```
┌─────────────────────────────────┬──────────────────────┐
│                                 │  In-Context Memories │
│   Conversation (scrollable)     │  ─────────────────── │
│                                 │  • Memory title A    │
│   Elroy: Lorem ipsum dolor...   │  • Memory title B    │
│   streaming in real time        │  • Memory title C    │
│                                 │                      │
│                                 │  [press M to dismiss]│
│                                 │                      │
├─────────────────────────────────┴──────────────────────┤
│  > user input here                                      │
├─────────────────────────────────────────────────────────┤
│  ● gpt-4o  ◌ bg-ingest: idle  ◌ memory-sync: 2m ago   │
└─────────────────────────────────────────────────────────┘
```

The memory panel collapses (M to toggle), the status footer collapses (S to toggle). Both state preferences persist for the session.

---

## Screens / Components

### 1. Conversation pane (`RichLog`)
- Occupies the main content area, left side when memory panel is open
- AI response streams token-by-token into the log, appended as Rich `Text`
- User messages appear immediately above the AI response in a distinct style
- Code blocks render with `Syntax` highlighting (already done by `RichFormatter`)
- Tool calls and results appear inline as dimmed system messages
- Full scroll history — user can scroll up while a response is still streaming
- A loading indicator (spinner) shows while waiting for the first token

### 2. In-Context Memories panel (`ListView`, right sidebar)
- Shows titles of memories currently in the context window (same data as today's `print_memory_panel`)
- Updates after each exchange without redrawing the conversation
- Toggled with `M` key; when dismissed, conversation pane expands to full width
- Default state: visible

### 3. Input bar
- Single-line `Input` widget at the bottom, always visible
- Retains slash-command completion (`/remember`, `/forget`, etc.) — reimplemented using Textual's `on_key` + suggestion logic
- Persistent input history (file-backed, same as today's `FileHistory`)
- Submit on Enter; Ctrl-C cancels in-progress stream; Ctrl-D exits

### 4. Status footer
- Single line at the very bottom, below input
- Always-on fields: active chat model name
- Conditional fields (shown when relevant):
  - Background ingestion: `idle` / `running` / `last run: Xm ago`
  - Memory file sync: `idle` / `syncing` / `last sync: Xm ago`
- Toggled with `S` key to show an expanded **System Status panel** (modal or slide-up) with full detail: DB path, ChromaDB path, memory dir, scheduler job states
- Default state: footer visible, expanded panel hidden

---

## Behaviors

### Streaming
- LLM stream runs as a Textual `worker` (background task on the asyncio loop)
- Each yielded token is posted to the app via `call_from_thread` or `post_message`
- The conversation pane appends each token without clearing previous content
- While streaming: input bar is disabled, spinner shows in footer
- Ctrl-C during stream: cancels the worker, rolls back DB, re-enables input

### Memory panel updates
- After each completed exchange, the memory panel refreshes its list
- No screen redraw — only the `ListView` items are replaced
- If panel is dismissed, the update still happens in the background so it's current when re-opened

### Status footer updates
- Background job states are polled from APScheduler every ~5 seconds via a Textual `set_interval` timer
- No user action required — footer updates reactively

---

## Key bindings

| Key | Action |
|-----|--------|
| `Enter` | Submit message |
| `M` | Toggle memory panel |
| `S` | Toggle system status footer / open detail panel |
| `Ctrl-C` | Cancel in-progress stream |
| `Ctrl-D` | Exit |
| `↑` / `↓` | Input history (when input focused) |
| `Tab` | Slash command completion |
| `Page Up/Down` | Scroll conversation |

---

## Implementation scope

### New
- `elroy/io/textual_app.py` — `ElroyApp(App)`, layout, key bindings, workers
- `elroy/io/widgets/` — `ConversationPane`, `MemoryPanel`, `StatusFooter`, `SystemStatusModal`

### Adapted
- `RichFormatter` — kept as-is; its Rich renderables work inside `RichLog`
- `ElroyIO` — `TextualIO` subclass replaces `CliIO`; implements same interface (`print`, `print_stream`, `prompt_user`, `info`, `warning`)
- `chat.py` `handle_chat` — thin wrapper that launches `ElroyApp` instead of the `while True` prompt loop

### Unchanged
- `PlainIO` / stdio path (API, piped usage)
- All messenger, memory, tool, and DB logic
- `RichFormatter` message types

---

## Out of scope
- Mobile / web rendering
- Mouse-driven memory panel interactions (keyboard-only for v1)
- Editing past messages
- Multi-session tabs
