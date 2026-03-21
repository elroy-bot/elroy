# PRD: Elroy Product Vision

**Status**: Draft
**Date**: 2026-03-20

---

## What is Elroy?

Elroy is a **memory-augmented AI personal assistant** for the command line. It wraps a large language model with persistent memory, reminders, agenda tracking, and document understanding — so every conversation benefits from what the assistant already knows about you.

It is designed for individuals who prefer working in a terminal, want an AI assistant they can script and automate, and don't want to re-explain context every session.

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

## Current Capabilities

### Memory
Automatically extracts facts from conversations, stores them as vector-embedded markdown files, surfaces relevant memories in future conversations, and periodically consolidates redundant entries. Supports Obsidian sync via a configurable `memory_dir`.

See: [prd-memory.md](prd-memory.md)

### Reminders
Time-based and context-triggered reminders. The assistant surfaces due reminders during relevant conversations. Full lifecycle management (create, update, delete, complete).

### Agenda / Task Tracking
Daily agenda items organized by date. Basic add/complete/delete flow. Expanding to support checklist sub-items and timestamped text updates.

See: [prd-agenda-item-tracking.md](prd-agenda-item-tracking.md)

### Document Understanding
Ingest documents (text, markdown) into a searchable store. RAG-style retrieval surfaces relevant excerpts in context. Background ingestion watches a configurable directory.

### Multiple Interfaces
- **TUI** — Textual-based terminal UI with streaming responses, memory sidebar, slash-command autocomplete
- **CLI** — Single-command mode for scripting (`echo "what did we discuss?" | elroy`)
- **Python API** — `from elroy import Elroy` for programmatic use in scripts and applications

### Multi-Model Support
OpenAI (GPT-4o, o1), Anthropic (Claude 3.5 Sonnet, Opus), Google Gemini, and any OpenAI-compatible API via LiteLLM. Model aliases (`--sonnet`, `--4o`) for quick selection.

---

## Product Priorities

The following areas represent the most impactful improvements, ordered roughly by user value and implementation feasibility.

---

### Priority 1: Memory Quality & Reliability

Memory is the core differentiator. Before adding new features, memory must be accurate, deduplicated, and surfaced at the right moment.

**Gaps**:
- Consolidation does not resolve contradictions in merged memories
- Recency is not a factor in recall ranking — old memories compete equally with recent ones
- Reflection word limit is hardcoded and inflexible
- Update-memory tool has no test coverage
- Archived memories accumulate with no cleanup path
- Consolidation has an N+1 query performance problem

**Goals**: See [prd-memory.md](prd-memory.md) for full detail.

---

### Priority 2: Agenda & Task Tracking

The agenda system is the user's primary way to manage structured work. It must support real task tracking, not just plain-text notes.

**Gaps**:
- No sub-task (checklist) support
- No progress notes over time
- List view does not show completion status of sub-tasks

**Goals**: See [prd-agenda-item-tracking.md](prd-agenda-item-tracking.md) for full detail.

---

### Priority 3: Reminders — Recurrence & Snooze

**Current state**: One-shot time-based or context-based reminders only.

**Gaps**:
- No recurring reminders (daily standup, weekly review)
- No snooze / defer (push a reminder forward by N hours/days)
- No batch management (list all reminders due this week)

**Goals**:
- Add `recurrence` field to reminders: `daily`, `weekly`, `monthly`, or cron expression
- Add `snooze_reminder(item_name, duration)` tool: pushes `trigger_datetime` forward
- Update `list_reminders_cmd` to support date-range filtering

---

### Priority 4: Memory Discoverability

**Current state**: Memories can be searched via `examine_memories` (semantic search) and `search_memories` (user-only). There is no browsing, filtering, or tagging.

**Gaps**:
- No way to browse memories by topic or time period
- No tagging or categorization
- Memory timeline is not visible
- Archived memories have no management UI

**Goals**:
- Add `list_memories_by_date(ctx, start_date, end_date)` user-only tool
- Add optional `tags` field to memory frontmatter; expose `tag_memory` and `search_memories_by_tag` tools
- Add `list_archived_memories` and `purge_archived_memories` tools (covered in memory PRD)

---

### Priority 5: REST API / HTTP Interface

**Current state**: Elroy is accessible only as a Python library or via CLI. There is no HTTP interface.

**Gap**: Integrating Elroy into other tools (scripts, web hooks, other apps) requires spawning a subprocess or importing Python directly.

**Goal**: Add an optional HTTP server mode (`elroy serve`) with:
- `POST /message` — send a message, get a response (streaming via SSE)
- `GET /memories` — list active memories
- `GET /reminders` — list active reminders
- Authentication via a configurable API key
- JSON request/response bodies following existing context conventions

This is the foundation for future integrations (Slack, Discord, Raycast, etc.).

---

### Priority 6: Processing Transparency

**Current state**: The TUI status bar shows a generic "⠋ thinking..." spinner from the moment the user submits a message until the full response is complete. The underlying pipeline — memory recall classification, vector search, LLM completion, tool execution, context persistence — is completely opaque. The `LatencyTracker` already instruments every phase internally (logged at DEBUG level); none of it surfaces to the user.

**Gap**: Users have no visibility into what is taking time. A 3-second pause before a response could be memory consolidation, a slow tool call, or a large LLM context — the user can't tell. This makes the assistant feel unreliable rather than deliberate.

**Goal**: The status bar (and equivalent output in CLI/PlainIO mode) should update in real time as the pipeline progresses.

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

### Priority 7: TUI Improvements

**Current state**: The TUI provides a functional terminal interface but has several usability gaps.

**Gaps**:
- Memory sidebar (`F2`) is read-only — cannot edit or delete memories from the sidebar
- Internal thought display is on by default and can be overwhelming for casual users
- No help screen for available slash commands

**Goals**:
- Memory sidebar: add `D` (delete) and `E` (edit) keybindings to selected memory
- Change `show_internal_thought` default to `false` (breaking change, needs migration note)
- Add `/help` slash command that renders a table of available commands with their docstrings

---

### Priority 8: Data Portability

**Current state**: Memories are backed by markdown files, making read access easy. But there is no standard export for the full dataset (memories + reminders + agenda items), and no import path.

**Goal**:
- Add `elroy export --output <dir>` CLI command that writes all active data to a structured directory of markdown files (one subdirectory per feature)
- Add `elroy import --input <dir>` that re-ingests an export bundle (idempotent, skips existing records by content hash)
- Document the export format so users can migrate between machines or back up to git

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
