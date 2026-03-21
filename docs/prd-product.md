# PRD: Elroy Product Vision

**Status**: Draft
**Date**: 2026-03-20

---

## What is Elroy?

Elroy is a **memory-augmented AI personal assistant** for the command line. It wraps a large language model with persistent memory, reminders, agenda tracking, and document understanding — so every conversation benefits from what the assistant already knows about you.

It is designed for individuals who prefer working in a terminal and don't want to re-explain context every session.

---

## Target Users

**Primary**: Developers and power users who live in a terminal.
- Want an AI assistant that remembers previous conversations
- Prefer a polished CLI experience over scriptability and automation
- Comfortable configuring tools via YAML and CLI flags

**Secondary**: Knowledge workers managing personal information (notes, reminders, recurring tasks).
- Use Obsidian or similar markdown-based note systems
- Want AI to surface relevant context without manual search
- Track to-dos, goals, and projects over months, not just days

---

## Core Value Proposition

> An AI assistant that remembers you — and gets smarter about you over time — without requiring a cloud account, a subscription UI, or manual note-taking.

---

## Capabilities

### Memory
Automatically extracts facts from conversations, stores them as vector-embedded markdown files, surfaces relevant memories in future conversations, and periodically consolidates redundant entries. Supports Obsidian sync via a configurable `memory_dir`.

See: [prd-memory.md](prd-memory.md)

### Reminders
Time-based and context-triggered reminders, including recurring schedules and snooze/defer. The assistant surfaces due reminders during relevant conversations. Full lifecycle management (create, update, delete, complete, snooze).

### Agenda / Task Tracking
Daily agenda items organized by date. Items support checklist sub-tasks with independent completion state and optional due dates, plus append-only timestamped progress notes.

See: [prd-agenda-item-tracking.md](prd-agenda-item-tracking.md)

### Document Understanding
Ingest documents (text, markdown) into a searchable store. RAG-style retrieval surfaces relevant excerpts in context. Background ingestion watches a configurable directory.

### Interface
- **TUI** — Textual-based terminal UI with streaming responses, memory sidebar, slash-command autocomplete, and real-time pipeline status
- **CLI** — Single-command mode (`echo "what did we discuss?" | elroy`)

### Multi-Model Support
OpenAI (GPT-4o, o1), Anthropic (Claude 3.5 Sonnet, Opus), Google Gemini, and any OpenAI-compatible API via LiteLLM. Model aliases (`--sonnet`, `--4o`) for quick selection.

---

## Product Priorities

The following areas represent the most impactful improvements, ordered roughly by user value and implementation feasibility.

---

### Priority 1: Memory Quality & Reliability

Memory is the core differentiator. Before adding new features, memory must be accurate, deduplicated, and surfaced at the right moment.

**Goals**: See [prd-memory.md](prd-memory.md) for full detail.

---

### Priority 2: Agenda & Task Tracking

The agenda system is the user's primary way to manage structured work.

**Goals**: See [prd-agenda-item-tracking.md](prd-agenda-item-tracking.md) for full detail.

---

### Priority 3: Reminders — Recurrence & Snooze

**Goals**:
- Add `recurrence` field to reminders: `daily`, `weekly`, `monthly`, or cron expression
- Add `snooze_reminder(item_name, duration)` tool: pushes `trigger_datetime` forward
- Update `list_reminders_cmd` to support date-range filtering

---

### Priority 4: Memory Discoverability

**Goals**:
- Add `list_memories_by_date(ctx, start_date, end_date)` user-only tool
- Add optional `tags` field to memory frontmatter; expose `tag_memory` and `search_memories_by_tag` tools
- Add `list_archived_memories` and `purge_archived_memories` tools (covered in memory PRD)

---

### Priority 5: Processing Transparency

The TUI status bar and CLI output should update in real time as the pipeline progresses, giving users visibility into what the assistant is doing.

**Proposed status messages**:

| Pipeline phase | Status bar text |
|----------------|----------------|
| Memory recall classification | `⠋ checking memory relevance…` |
| Memory vector search | `⠋ recalling memories…` |
| Due reminders check | `⠋ checking reminders…` |
| LLM completion (first loop) | `⠋ thinking…` |
| Tool execution | `⠋ running: <tool_name>…` |
| Memory consolidation (background) | *(non-blocking; shown in sidebar or as a transient notice)* |
| Context persistence | *(silent; too fast to surface)* |

**Implementation notes**:
- The messenger's generator already yields typed stream chunks (`AssistantInternalThought`, `FunctionCall`, token strings). Add a new `ProcessingStatus` yield type (a lightweight dataclass with a `message: str` field) emitted at each phase boundary.
- `TextualIO` and `PlainIO` consume the stream; `PlainIO` can print status lines to stderr so they don't pollute piped output.
- The `_run_stream` loop in `textual_app.py` handles each item type; add a branch for `ProcessingStatus` that calls `_update_status_bar(message)`.
- Background consolidation is fire-and-forget; surface it as a brief sidebar notice ("Consolidating memories…") rather than blocking the status bar.
- No new config needed — this is always-on behavior.

**Acceptance criteria**:
- Submitting a message that triggers memory recall causes the status bar to read `⠋ recalling memories…` before switching to `⠋ thinking…`
- A tool call that takes > 0.5s shows `⠋ running: <tool_name>…` for its duration
- `echo "hi" | elroy` (PlainIO mode) produces status lines on stderr only, with `--quiet` suppressing them
- Existing snapshot/integration tests are not broken by the new yield type

---

### Priority 6: TUI Improvements

**Goals**:
- Memory sidebar: add `D` (delete) and `E` (edit) keybindings to selected memory
- Change `show_internal_thought` default to `false` (breaking change, needs migration note)
- Add `/help` slash command that renders a table of available commands with their docstrings

---

## Non-Priorities (Explicit)

The following are **out of scope** for the foreseeable future:

- **Multi-user / team features** — Elroy is a personal assistant; sharing memory across users introduces complexity and privacy concerns not appropriate for the current stage.
- **GUI / web app** — the TUI and CLI are the primary interfaces. A web UI would require significant investment and diverge from the terminal-native positioning.
- **Voice interface** — not aligned with CLI-first users.
- **Plugin marketplace** — custom tools are supported via Python; a formal plugin system is premature.

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Memory precision (relevant memories recalled / total recalled) | > 80% in user testing |
| Consolidation reduces memory count by | ≥ 30% after 50 conversations |
| Recall classifier skip rate | 40–60% (neither too aggressive nor too permissive) |
| Agenda checklist feature adoption | Used in ≥ 50% of agenda items after launch |
| Time-to-first-useful-memory | ≤ 3 conversations from first install |
| Test coverage (overall) | ≥ 80% line coverage |

---

## Architecture Principles

These principles should guide all future development:

1. **Memory first** — every feature should consider how it interacts with the memory system. New structured data (agenda items, reminders) should be candidatesfor memory extraction.
2. **File-backed where possible** — markdown + YAML frontmatter is the persistence format for user-visible data. Database rows are indexes, not sources of truth.
3. **Config-driven, not code-driven** — behavioral tuning (thresholds, intervals, limits) belongs in config, not in code.
4. **Minimal configuration, sensible defaults** — a fresh install with zero configuration should work well for the typical user. New options should only be added when the right behavior genuinely varies by user or environment, and every option must have a default that is correct without any tuning. Prefer removing a config knob over proliferating them.
5. **Tool-centric agent loop** — the assistant gains capabilities through tools, not special-cased prompt logic.
6. **No breaking changes without migration** — schema migrations via Alembic; config changes with documented deprecation path.
