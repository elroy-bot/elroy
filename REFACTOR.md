# Textual Refactor Implementation Plan

This document is the implementation plan for bringing Elroy's TUI closer to Textual-native patterns. It replaces the previous analysis-oriented version of this file with an ordered task list that can be executed incrementally.

The plan is organized so each phase leaves the app in a working state, reduces custom UI infrastructure, and sets up the next phase cleanly.

## Goal

Move the TUI away from custom slash-command routing, CLI-shaped prompting, and mixed background execution models, and toward:

- Textual command palette and command providers
- Textual screens and form-driven command input
- Textual worker groups and worker lifecycle events
- Textual-native pane switching and binding discovery
- Clearer separation between Textual UI orchestration and core domain logic

## Constraints

- Keep repository and messenger logic framework-agnostic.
- Keep the app usable after each phase.
- Preserve slash command compatibility until palette and form flows are complete.
- Prefer deleting custom UI code over adding another compatibility layer.
- Extend TUI tests as part of each phase, not after the full refactor.

## Current State Summary

The main issues this plan addresses are:

- Slash commands are parsed manually in `elroy/io/textual_app.py` and dispatched through `elroy/messenger/slash_commands.py`.
- Multi-argument commands still depend on `ElroyIO.prompt_user(...)`, which is a CLI-style abstraction that does not fit a widget-first TUI.
- UI-triggered background work is split across Textual workers, APScheduler threads, raw background threads, and thread-pool utilities.
- Worker state is represented with manual flags and timers instead of Textual worker groups and worker events.
- The sidebar reimplements tab switching and focus logic that Textual already provides.
- Keybinding guidance is embedded in a custom status bar instead of using Textual’s binding-discovery affordances.

## Phase 1: Command Palette Foundation

Objective:

- Make the Textual command palette the primary discovery and invocation surface for TUI commands.

Tasks:

1. Add a command module for the TUI.
   - Create a module such as `elroy/io/textual_commands.py`.
   - Define app-level command registration in one place.
   - Introduce a small command metadata structure so UI commands are not inferred ad hoc from slash parsing.

2. Implement app-level system commands.
   - Add `ElroyApp.get_system_commands(...)`.
   - Expose high-value zero-argument actions first:
     - toggle memory panel
     - refresh system instructions
     - reset messages
     - focus memories
     - focus agenda
     - open help/about command view if needed

3. Add one or more Textual command providers.
   - Provide searchable command entries for memory, reminder, agenda, and preference actions.
   - Reuse existing tool docstrings and names where possible, but stop treating slash parsing as the source of truth.

4. Keep slash commands as compatibility only.
   - Keep `/...` support working.
   - Route slash-command execution through the same action layer used by the palette where practical.
   - Stop growing `elroy/messenger/slash_commands.py` as a TUI-specific abstraction.

5. Update in-app affordances.
   - Teach the user the command palette shortcut in the status/help surface.
   - Stop presenting `/help` as the primary TUI discovery path.

Acceptance criteria:

- Users can discover and run core TUI actions through the command palette.
- Zero-argument UI actions no longer require slash syntax.
- Slash commands still work, but the palette is the documented primary path.

Files likely affected:

- `elroy/io/textual_app.py`
- `elroy/io/textual_commands.py` (new)
- `elroy/messenger/slash_commands.py`
- `README.md`
- `tests/io/test_textual_app.py`

## Phase 2: Modal Command Forms

Objective:

- Replace CLI-style prompt loops with Textual-native modal forms for argument-bearing commands.

Tasks:

1. Introduce reusable command form screens.
   - Add a generic `CommandFormScreen` for commands with structured parameters.
   - Add a `ConfirmActionScreen` where destructive actions currently rely on lightweight ad hoc confirmation patterns.

2. Move argument collection into widgets.
   - Use `Input` widgets for form fields.
   - Add validators, field hints, and optional-field handling.
   - Use suggesters for fixed or semi-fixed inputs where that improves speed and correctness.

3. Route command submission through explicit UI actions.
   - Form submission should launch a command action, not call `prompt_user(...)`.
   - Validation errors should stay in the modal instead of being dumped into chat history.

4. Shrink the TUI dependency on `ElroyIO.prompt_user(...)`.
   - Remove TUI reliance on prompt loops for multi-argument slash commands.
   - Leave CLI behavior intact where non-Textual interfaces still need prompt-driven flows.

5. Decide how form outcomes are surfaced.
   - Conversational results stay in history.
   - Ephemeral confirmations use toasts where appropriate.

Acceptance criteria:

- Multi-argument actions can be launched from the palette and completed in a modal form.
- The TUI no longer depends on sequential prompt loops for command arguments.
- Form validation is widget-native and test-covered.

Files likely affected:

- `elroy/io/textual_app.py`
- `elroy/io/textual_commands.py`
- `elroy/io/textual_forms.py` or similar (new)
- `elroy/messenger/slash_commands.py`
- `elroy/io/base.py`
- `tests/io/test_textual_app.py`

## Phase 3: Worker Consolidation

Objective:

- Move UI-owned asynchronous work onto explicit Textual worker groups and simplify worker state handling.

Tasks:

1. Assign worker groups to existing app background flows.
   - Suggested groups:
     - `session-bootstrap`
     - `chat-stream`
     - `sidebar-refresh`
     - `command-action`
     - `deferred-context-refresh`

2. Refactor chat processing around explicit worker ownership.
   - Make `_process_input(...)` clearly run under chat or command worker groups.
   - Stop using `self.workers.cancel_all()` for stream cancellation.
   - Cancel only the relevant worker group.

3. Consolidate sidebar and completion refresh work.
   - Merge `_refresh_memory_panel(...)` and `_update_completions(...)` if they fetch overlapping state.
   - Return structured results from workers rather than mutating many fields piecemeal from worker threads.

4. Introduce worker lifecycle handling.
   - Handle worker completion, failure, and cancellation centrally.
   - Use worker state transitions to drive status updates and error display.

5. Reduce manual spinner state where worker state can replace it.
   - Keep a global status indicator for streaming/model activity.
   - Remove duplicated state flags that exist only because worker lifecycle is not being used directly.

Acceptance criteria:

- UI-triggered background actions are grouped and cancellable by intent.
- Chat cancellation targets chat work only.
- Status and busy-state behavior are driven primarily by worker lifecycle, not custom booleans.

Files likely affected:

- `elroy/io/textual_app.py`
- `elroy/io/textual_io.py`
- `tests/io/test_textual_app.py`

## Phase 4: Remove Legacy Threading From The TUI Path

Objective:

- Eliminate non-Textual concurrency mechanisms from UI-owned flows.

Tasks:

1. Audit UI call paths for background execution helpers.
   - Identify all TUI-triggered uses of:
     - `run_in_background(...)`
     - `ctx.thread_pool`
     - `schedule_task(...)` for short-lived UI follow-up work

2. Migrate UI-local deferred actions onto Textual workers.
   - Replace TUI-owned delayed refresh/synchronization work with worker-driven follow-up where feasible.
   - Keep APScheduler only for truly app-agnostic scheduled jobs.

3. Clarify session creation rules for worker code.
   - Ensure worker bodies create or use safe DB/session boundaries.
   - Stop duplicating session recreation logic across multiple unrelated UI helpers.

4. Reduce TUI coupling to thread-pool semantics.
   - Remove TUI dependencies on `ElroyContext.thread_pool` where no longer needed.
   - Narrow `ElroyIO` interfaces if Textual-specific prompt behavior is no longer required.

Acceptance criteria:

- UI-owned background work no longer depends on raw background thread helpers.
- APScheduler remains only where it serves non-UI scheduling concerns.
- The Textual app has one primary concurrency model for app-driven background work.

Files likely affected:

- `elroy/io/textual_app.py`
- `elroy/utils/utils.py`
- `elroy/core/async_tasks.py`
- `elroy/core/ctx.py`
- `elroy/io/base.py`
- tests touching background behavior

## Phase 5: Sidebar And Navigation Cleanup

Objective:

- Replace custom sidebar section and browse-mode behavior with more native Textual navigation primitives.

Tasks:

1. Replace the custom memories/agenda section header.
   - Use `Tabs` plus `ContentSwitcher`, or `TabbedContent`, depending on how much control the layout needs.

2. Simplify focus and selection logic.
   - Push section-switching state into widgets.
   - Delete manual state that only mirrors widget state.

3. Reduce `on_key(...)` complexity.
   - Move behavior into actions and widget-native focus/navigation where possible.
   - Keep only high-value custom shortcuts that are genuinely product-specific.

4. Re-evaluate browse mode.
   - Determine whether browse mode still needs to exist as an explicit app-level concept once tabs and focus behavior are native.
   - Remove it if it no longer provides unique value.

5. Consider widget-local loading states.
   - Use local loading indicators for sidebar refreshes if that improves clarity over global status text alone.

Acceptance criteria:

- Sidebar section switching is handled by Textual-native widgets.
- The amount of app-owned focus/navigation code drops materially.
- The app is easier to extend without editing a single large `on_key(...)` branch.

Files likely affected:

- `elroy/io/textual_app.py`
- `tests/io/test_textual_app.py`

## Phase 6: Binding Discovery And Status Surface Cleanup

Objective:

- Let Textual own binding discovery and reduce custom status-bar responsibility.

Tasks:

1. Add a `Footer`.
   - Expose relevant bindings through Textual’s standard UI.
   - Use `show=False` for actions that should remain hidden.

2. Use action availability checks.
   - Add `check_action(...)` where mode- or context-dependent actions should be disabled or hidden.

3. Shrink the custom status bar.
   - Keep model name, worker activity, and background status if useful.
   - Remove embedded keybinding instructions once the footer is in place.

4. Review whether a `Header` is warranted.
   - Default answer: probably not now.
   - Only add it if later phases introduce enough multi-screen/app-shell complexity to justify the vertical space.

Acceptance criteria:

- Binding discovery is primarily handled by the footer.
- The custom status area focuses on runtime status, not instruction text.

Files likely affected:

- `elroy/io/textual_app.py`
- `tests/io/test_textual_app.py`

## Phase 7: Testing And Regression Coverage

Objective:

- Keep the TUI refactor safe by extending Textual-specific tests as each phase lands.

Tasks:

1. Add command-palette coverage.
   - Opening the palette
   - Invoking zero-argument commands
   - Launching argument-bearing commands

2. Add modal form coverage.
   - Validation behavior
   - Cancel behavior
   - Successful submission behavior

3. Add worker-behavior coverage.
   - Stream cancellation
   - Worker failure handling
   - Sidebar refresh behavior

4. Add navigation coverage.
   - Sidebar tab switching
   - Focus behavior after modal close
   - Keyboard navigation for remaining custom shortcuts

5. Evaluate snapshot tests for stable UI surfaces.
   - Use only where the screen structure is stable enough to justify the maintenance cost.

Acceptance criteria:

- Each refactor phase adds or updates TUI tests alongside implementation.
- The suite protects the new command, worker, and navigation behaviors from regression.

Files likely affected:

- `tests/io/test_textual_app.py`
- any new snapshot or pilot-driven UI test modules

## Optional Follow-Up Tasks

These are useful, but not on the critical path:

1. Introduce screen-scoped command providers for modal/detail screens.
2. Evaluate `MODES` if the app grows into distinct top-level workflows beyond a single chat shell.
3. Evaluate `Lazy` or `Reveal` mounting if the post-refactor UI grows heavier and startup responsiveness becomes an issue.

## Out Of Scope

- Rewriting repository/business logic to depend on Textual
- Removing APScheduler globally if it remains useful for non-UI scheduling
- Replacing the chat streaming model wholesale
- Forcing a fully async architecture where Textual thread workers remain a practical integration point

## Suggested Execution Order

Implement the phases in this order:

1. Phase 1: Command Palette Foundation
2. Phase 2: Modal Command Forms
3. Phase 3: Worker Consolidation
4. Phase 4: Remove Legacy Threading From The TUI Path
5. Phase 5: Sidebar And Navigation Cleanup
6. Phase 6: Binding Discovery And Status Surface Cleanup
7. Phase 7: Testing And Regression Coverage

## Completion Definition

This refactor is complete when:

- The command palette is the primary TUI command surface.
- Multi-argument commands use Textual forms instead of prompt loops.
- UI-owned background work is managed through Textual workers and worker groups.
- Raw thread helpers are no longer part of normal TUI interaction flows.
- Sidebar section switching and keybinding discovery use Textual-native primitives.
- TUI behavior is covered by targeted Textual tests for commands, workers, and navigation.
