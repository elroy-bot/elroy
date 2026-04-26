# UI Architecture

`elroy.ui` is the canonical package for Elroy's Textual terminal UI.

## Package roles

- `app.py`
  App shell and top-level wiring.
- `widgets.py`
  Textual widgets and widget-local event translation.
- `state.py`
  Pure UI state and intent-mapping logic.
- `session.py`
  Session bootstrap, chat streaming, tool execution, and context refresh workflows.
- `sidebar.py`
  Sidebar read/mutation coordination.
- `status.py`
  Worker-group and status-bar coordination.
- `command_flow.py`
  Command lookup and launch/execute decision flow.
- `commands.py`
  Command metadata and palette provider integration.
- `forms.py`
  Textual command-form screens.
- `output.py`
  `TextualIO`, the bridge from streamed domain output into the TUI.

## Import policy

- Within `elroy.ui`, prefer relative imports for sibling modules.
- Outside `elroy.ui`, prefer absolute imports such as `elroy.ui.app`.
- `elroy.ui.__init__` should expose only a small curated public surface.
