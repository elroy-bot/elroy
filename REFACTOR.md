# Textual Refactor Plan

This document replaces the older context/repository refactor notes with a Textual-specific review of the TUI.

The current app is functional, but it often uses Textual as a rendering shell while preserving custom command routing, custom background execution, and custom focus/navigation logic that Textual already has first-class support for. The goal of this refactor is to move the TUI toward Textual-native patterns so the UI becomes easier to extend, easier to cancel safely, and less dependent on app-specific glue code.

## Why This Refactor

The current TUI already depends heavily on Textual:

- `elroy/io/textual_app.py` is the main application shell
- modal interactions already use `ModalScreen`
- several long-running actions already use `@work(thread=True)`

But a number of important workflows still bypass Textual’s built-in architecture:

- Slash commands are parsed manually in `ElroyApp._process_input` and dispatched through `elroy/messenger/slash_commands.py`
- Multi-argument commands still rely on `ElroyIO.prompt_user(...)` prompting semantics instead of Textual-native command or screen flows
- Background work is split across Textual workers, raw threads in `elroy/utils/utils.py`, and APScheduler threads in `elroy/core/async_tasks.py`
- Worker lifecycle is mostly managed manually through booleans, spinner timers, and `call_from_thread(...)` plumbing instead of worker groups and worker state events
- The sidebar implements custom section switching and browse-mode state that overlaps with Textual widgets such as `Tabs`, `TabbedContent`, or `ContentSwitcher`

## External Textual Guidance

This plan aligns with current Textual documentation:

- The command palette is built in and is intended for app and screen commands via `get_system_commands` and command `Provider` classes.
- Workers are managed through `run_worker`, `@work`, `WorkerManager`, worker groups, and `Worker.StateChanged` events.
- Thread workers are supported, but Textual expects their lifetime and cancellation to stay within its worker model rather than drifting into unrelated thread utilities.

Source references:

- https://textual.textualize.io/guide/command_palette/
- https://textual.textualize.io/guide/workers/
- https://textual.textualize.io/api/worker_manager/

## Current Mismatches

### 1. Custom Slash Command Layer Instead Of Textual Command Palette

Current state:

- `ElroyApp._process_input` checks `text.startswith("/")` and manually diverts into `invoke_slash_command(...)`
- `elroy/messenger/slash_commands.py` introspects callable signatures and prompts argument-by-argument through `ElroyIO`
- `README.md` presents `/help` and `/command` usage as the main TUI command surface

Why this is a mismatch:

- Textual already provides a command palette with discoverability, fuzzy search, screen scoping, and built-in invocation semantics.
- The current slash system duplicates command registration, discovery, help text, and command dispatch rules.
- Argument prompting through `ElroyIO.prompt_user(...)` is a CLI-era abstraction that does not map cleanly to a widget-based TUI.

Observed costs:

- Commands are hard to discover unless the user already knows the slash syntax.
- Command metadata is scattered across tool docstrings, the slash dispatcher, and ad hoc help output.
- Textual command actions cannot currently operate as first-class UI commands.

### 2. Background Work Is Split Across Three Concurrency Systems

Current state:

- Textual workers are used in `elroy/io/textual_app.py`
- `elroy/utils/utils.py` still exposes `run_in_background(...)` using raw daemon threads
- `elroy/core/async_tasks.py` uses APScheduler with its own thread pool
- `ctx.thread_pool` still exists as a separate execution mechanism

Why this is a mismatch:

- Textual already provides a worker manager tied to the app and DOM node lifetime.
- UI-triggered work should generally live in Textual workers so cancellation, shutdown, and error visibility are consistent.
- Multiple execution models increase the odds of stale UI updates, thread-local DB session bugs, and “cancelled in UI but still running in backend thread” behavior.

Observed costs:

- The app has to maintain custom streaming flags and timer state to represent background activity.
- Cancellation uses `self.workers.cancel_all()` at the UI layer, but non-Textual background tasks remain outside that lifecycle.
- Session recreation rules are duplicated between `run_in_background(...)` and `schedule_task(...)`.

### 3. Worker State Is Managed Manually Instead Of Through Worker Semantics

Current state:

- The app tracks `_streaming`, `_status_message`, `_spinner_handle`, and `_bg_status_handle`
- UI updates from background work are mostly coordinated by manual `call_from_thread(...)`
- The app does not meaningfully consume `Worker.StateChanged` events or worker grouping

Why this is a mismatch:

- Textual workers already expose grouping, exclusivity, progress, cancellation, and state transitions.
- Manual state machines are harder to reason about than worker lifecycle events.

Observed costs:

- The spinner and input-disabled state can drift from the actual worker lifecycle.
- “Cancel stream” is broad and imperative instead of targeted to a worker group such as `chat-stream`.
- There is no central place to observe or test worker success, error, or cancellation behavior.

### 4. Sidebar Section Switching Reimplements Tabbed Navigation

Current state:

- The “Memories” vs “Agenda” switch is implemented with labels, CSS classes, and app-level key handling
- The app stores `_sidebar_section`, `_browse_mode`, `_browse_target`, and per-section indices by hand

Why this is a mismatch:

- Textual has widgets built for section switching and focus management.
- The current approach couples model state, focus rules, keybindings, and rendering tightly inside `ElroyApp`.

Observed costs:

- A large amount of code in `textual_app.py` exists only to emulate common widget behavior.
- Keyboard behavior is harder to extend because navigation logic is centralized in one large `on_key(...)` path.

### 5. Command Input Behavior Is Still CLI-Shaped

Current state:

- `ChatInput` is a customized `TextArea`
- Tab completion is implemented manually against `_chat_suggestions`
- Slash command prompting relies on `prompt_user(...)`

Why this is a mismatch:

- Textual favors explicit widgets, screens, and providers for UI interaction rather than “pause and prompt for more stdin-like values.”
- Structured command entry should be handled through screens, forms, or command actions, not through a faux terminal prompt model embedded in a TUI.

Observed costs:

- Multi-step command input is awkward in the TUI.
- Command and chat input are over-coupled because both are funneled through the same text box semantics.

## Refactor Goals

1. Make the command palette the primary command surface for user-invoked TUI actions.
2. Keep slash commands only as a compatibility shim during migration, not the long-term UI architecture.
3. Consolidate UI-owned background work onto Textual workers and worker groups.
4. Replace UI-thread bookkeeping with worker lifecycle events where possible.
5. Move from custom browse-mode state toward Textual widgets that already encode tabs, sections, and focus behavior.
6. Isolate non-UI scheduling from UI interaction so only true background scheduling remains outside Textual.

## Proposed Changes

### A. Introduce A Textual Command Layer

Add a Textual-native command module, for example:

- `elroy/io/textual_commands.py`

This module should define:

- App-wide system commands via `ElroyApp.get_system_commands(...)`
- One or more command `Provider` classes for searchable domain actions
- A mapping layer from tool metadata to Textual commands

Suggested command categories:

- Chat/session actions
  - New chat
  - Refresh system instructions
  - Reset messages
  - Toggle memory panel
  - Focus memories
  - Focus agenda
- Memory actions
  - Search memories
  - Print memories
  - Create memory
  - Add memory to current context
- Agenda/reminder actions
  - List agenda items
  - Create due item
  - Show active reminders
- User preference actions
  - Set assistant name
  - Set preferred name

Design direction:

- Zero-argument commands can execute directly from the palette.
- Commands with arguments should open a Textual modal form screen instead of calling `prompt_user(...)`.
- `get_help` should stop being the primary discovery surface inside the TUI. The palette itself should provide discovery.

Migration note:

- Keep `/...` parsing only as a temporary compatibility path.
- The slash layer should become a thin adapter that invokes the same command actions used by the palette.

### B. Replace Command Prompting With Modal Screens

Create reusable command form screens, for example:

- `CommandFormScreen`
- `ConfirmActionScreen`

These should replace the current “inspect parameters, then prompt in sequence” flow in `elroy/messenger/slash_commands.py`.

Suggested behavior:

- Required parameters render as explicit fields
- Optional parameters render as optional fields with defaults or placeholders
- Submission launches the corresponding command worker
- Validation errors stay in the modal instead of being written back as generic history text

Benefits:

- Better fit for Textual’s screen model
- More testable than prompt loops
- Removes the need for `ElroyIO.prompt_user(...)` from the TUI path

### C. Consolidate UI Work Onto Textual Workers

UI-triggered asynchronous or threaded work should move under explicit worker groups.

Suggested groups:

- `session-bootstrap`
- `chat-stream`
- `sidebar-refresh`
- `completion-refresh`
- `command-action`
- `deferred-context-refresh`

Concrete changes:

- Keep `@work` for app-local background actions, but add `group=...`, `exclusive=True` where appropriate, and `exit_on_error=False` where the UI should degrade gracefully.
- Replace broad `self.workers.cancel_all()` with targeted group cancellation such as `self.workers.cancel_group("chat-stream")`.
- Track the active chat worker explicitly instead of relying on `_streaming` alone.
- Use `Worker.StateChanged` handling to drive status-bar state, completion of deferred refreshes, and user-visible error reporting.

Examples:

- `_process_input(...)` should become a `chat-stream` or `command-action` worker entrypoint.
- `_refresh_memory_panel(...)` and `_update_completions(...)` should probably be merged into one worker that returns a sidebar/completion snapshot.
- `_start_session(...)` should be a named bootstrap worker with clear completion/error behavior.

### D. Remove Raw UI Background Thread Helpers

For the Textual app, stop introducing new uses of:

- `elroy/utils/utils.py::run_in_background`
- `ctx.thread_pool`
- UI-local ad hoc thread usage outside Textual workers

Refactor direction:

- Keep raw thread or scheduler helpers only for truly non-UI runtime work.
- For anything initiated by the TUI or affecting widgets, use a Textual worker.
- If a worker needs a fresh DB session, create that session inside the worker body rather than outside the worker model.

Important distinction:

- APScheduler may still be appropriate for app-agnostic scheduled jobs.
- But those jobs should not be the mechanism by which the TUI manages its own short-lived refresh work.

### E. Replace Manual Status Plumbing With Worker-Aware Status

Current status handling is mostly custom.

Refactor toward:

- A small status model derived from active workers
- Worker-group-specific messages such as:
  - `chat-stream`: model/status update text
  - `sidebar-refresh`: refreshing sidebar
  - `command-action`: running command
- Optional progress reporting for long-running operations where meaningful

This should reduce the number of mutable flags on `ElroyApp` and make cancel/error states match actual worker state.

### F. Simplify The Sidebar With Native Section Widgets

Replace the custom header label switcher with a Textual-native section mechanism.

Likely options:

- `Tabs` plus a content switcher
- `TabbedContent` if the interaction model fits
- A narrower `ContentSwitcher` setup if full tabs are visually undesirable

Refactor result:

- The active section becomes widget state rather than hand-managed app state
- Keybindings can target widget actions instead of manual string flags
- A meaningful amount of `on_key(...)`, `_set_sidebar_section(...)`, and related browse bookkeeping can be deleted

### G. Clarify TUI vs Core Boundaries

The refactor should preserve a clean boundary:

- Core domain logic should remain outside Textual
- Textual should own view state, command discovery, worker lifecycle, modal flows, and focus/navigation
- Domain commands invoked from Textual should be thin adapters around repository tools/orchestrators

That means:

- Do not move repository/business logic into widgets
- Do move UI interaction orchestration out of CLI-era abstractions and into Textual screens/providers/actions

## Recommended Phases

### Phase 1: Command Surface

- Add palette commands through `get_system_commands(...)`
- Introduce command providers for searchable memory / reminder / session actions
- Keep slash parsing as compatibility only
- Update README and in-app status text to teach `Ctrl+P` instead of `/help` as the primary discovery path

### Phase 2: Command Forms

- Add modal form screens for argument-bearing actions
- Route palette commands and slash compatibility commands through the same action layer
- Remove TUI reliance on `ElroyIO.prompt_user(...)`

### Phase 3: Worker Consolidation

- Group existing `@work` methods
- Replace global cancellation with group cancellation
- Merge duplicated sidebar/completion workers where it reduces duplicate data fetches
- Introduce `on_worker_state_changed(...)` handling for status and errors

### Phase 4: Remove Legacy Threading From The TUI Path

- Stop using `run_in_background(...)` from UI-owned flows
- Audit `schedule_task(...)` calls triggered directly from the TUI
- Move short-lived deferred UI follow-up work onto Textual workers

### Phase 5: Sidebar And Navigation Cleanup

- Replace custom sidebar section headers with tabs or a content switcher
- Reduce `on_key(...)` branching by delegating more behavior to widgets and actions
- Revisit whether “browse mode” needs to exist as a custom state at all

## Non-Goals

- Rewriting repository or messaging logic to be Textual-specific
- Eliminating APScheduler globally if it still serves non-UI scheduled jobs well
- Replacing streaming output with a totally different chat architecture
- Forcing async I/O throughout the codebase if threaded workers remain the practical integration path

## Expected Benefits

- Better command discoverability through Textual’s built-in palette
- Fewer app-specific input and prompt abstractions
- Cleaner cancellation and shutdown semantics
- Less drift between worker lifecycle and UI state
- Smaller `ElroyApp` surface area with more responsibility delegated to Textual-native primitives
- Easier testing because commands, workers, and modal flows become explicit UI units

## Initial Priority Order

If this refactor is done incrementally, the recommended order is:

1. Command palette adoption
2. Modal command forms
3. Worker-group consolidation
4. Sidebar widget cleanup
5. Removal of remaining TUI-specific legacy thread helpers

This order delivers the biggest usability and architecture wins first without requiring a full UI rewrite.
