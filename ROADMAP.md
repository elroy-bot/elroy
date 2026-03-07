# Elroy Roadmap

This document tracks planned improvements and features for Elroy.

## Current Priorities

(No active priorities at this time)

## Future Items

(Items will be added here as they are identified)

## UI / TUI Specification

### Textual TUI (current)

The TUI is implemented in `elroy/io/textual_app.py` using the [Textual](https://textual.textualize.io/) framework.

#### Layout
- **Left panel**: scrolling `RichLog` (history) + `Static` streaming buffer below
- **Right panel** (toggleable, `F2` key): in-context memories sidebar, 36 columns wide
- **Input bar**: full-width `Input` widget with slash-command autocomplete and up/down history
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

## Completed

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
