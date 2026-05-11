# Elroy Roadmap

This document tracks planned improvements and features for Elroy.

## Current Priorities

- **Build async Codex agent workflow on an `agent` branch**
  - Run Codex coding sessions asynchronously so Elroy remains available for chat while work is in progress
  - Isolate each coding session in its own branch/worktree before integrating results
  - Merge successful session output into a long-lived `agent` branch instead of `main`
  - Treat `agent` as the primary branch Elroy should run on for agent-driven improvements
  - Trigger an assistant response automatically when a background Codex session completes

## Future Items

- Add built-in filesystem read tools for agent workflows
  - Include `pwd`, bounded recursive `ls`, and `read_file`
  - Keep listings capped to reduce tool-call churn without flooding context

## UI / TUI Specification

### Textual TUI (current)

The TUI is implemented under `elroy/ui/` using the [Textual](https://textual.textualize.io/) framework.

#### Layout
- **Left panel**: `ConversationPane` with scrolling `RichLog` history + live streaming buffer
- **Right panel**: context sidebar, 36 columns wide
- **Input bar**: full-width `ChatInput` (`TextArea`) with slash-command completion and up/down history
- **Status bar**: model name or "⏳ streaming..." indicator

#### Color Differentiation (required — must be preserved)

All message types must render with visually distinct colors. These are configured via
`UIConfig` defaults (`elroy/core/configs.py`) and applied by `RichFormatter` (`elroy/io/formatters/rich_formatter.py`):

| Message type | Style | Default color (from `defaults.yml`) |
|---|---|---|
| User input | plain | `#FFE377` (`user_input_color`) |
| Assistant response | plain | `#77DFD8` (`assistant_color`) |
| Agent internal thought | italic | `#708090` slate gray (`internal_thought_color`) |
| Function call (name) | bold | `#9ACD32` yellow-green (`system_message_color`) |
| Tool result (success) | plain | `#9ACD32` yellow-green (`system_message_color`) |
| Tool result (error) | plain | `yellow` (`warning_color`) |
| System info | plain | `#9ACD32` yellow-green (`system_message_color`) |
| System warning | plain | `yellow` (`warning_color`) |

Internal thoughts are **shown by default** (`show_internal_thought = true` in `defaults.yml`).
They can be hidden via `--no-show-internal-thought` or `show_internal_thought: false` in config.

#### Streaming architecture
- `AssistantResponse` tokens accumulate in `_streaming_buffer` (shown live in `Static#streaming-output`)
- On stream end, the buffer is flushed as a single `Text` object to `RichLog#history-log`
- All other message types write directly to `RichLog` via `RichFormatter.format()`

#### Package structure
- `elroy/ui/app.py` — app shell and top-level wiring
- `elroy/ui/widgets.py` — Textual widgets such as `ConversationPane`, `SidebarPanel`, and `StatusBar`
- `elroy/ui/state.py` — pure UI decision/state models
- `elroy/ui/session.py`, `sidebar.py`, `status.py`, `command_flow.py` — UI-side controllers

## Completed

### Developer Experience
- **Add self-restart tool for autonomous tool/code refresh** (Completed: 2026-05)
  - Added assistant-visible `restart_session` support to request a graceful TUI restart
  - Re-executes Elroy after the current response completes so updated code and tools are loaded
  - Shows an automatic assistant resume message after restart to continue the session cleanly

### Developer Experience
- **Add Codex session dispatch tools** (Completed: 2026-05)
  - Added assistant-visible tools to dispatch, resume, and list Codex sessions
  - Grounded Codex runs to repositories inside the `development` workspace
  - Persisted Codex session ids and latest change summaries for later resumption

### Performance
- **Improve latency tracking and logging** (Completed: 2025-01)
  - Added comprehensive latency tracking module (`elroy/core/latency.py`)
  - Implemented `LatencyTracker` class for tracking operations across requests
  - Added context manager for measuring operations with automatic logging
  - Built summary functionality showing breakdown by operation type
  - Added decorators for tracking function latency
  - Configured automatic logging for slow operations (>100ms)

### Developer Experience
- **Create Claude Code skills for memory tools** (Completed: 2025-01)
  - Built complete set of 6 Claude Code skills in `claude-skills/` directory
  - `/remember` - Create long-term memories
  - `/recall` - Search through memories
  - `/list-memories` - List all active memories
  - `/remind` - Create reminders
  - `/list-reminders` - List active reminders
  - `/ingest` - Ingest documents into memory
  - Includes installation script with help documentation
