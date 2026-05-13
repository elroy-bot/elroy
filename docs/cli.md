# CLI

Elroy provides a terminal UI (TUI) for interacting with the AI assistant directly from your terminal.

## Starting Elroy

```bash
# Open the interactive chat interface
elroy
```

This opens a full-screen terminal application where you can chat with the assistant, create memories, and manage agenda or due items.

## Command Palette

Use the Textual command palette to run built-in tools and actions from the TUI.

For a full list of available tools, see the [Tools Guide](tools_guide.md).

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+D` | Exit |
| `Ctrl+C` | Cancel current response |
| `F2` | Toggle memory panel |

## Configuration

Elroy is configured via environment variables or a config file — there are no command-line flags. See the [Configuration Guide](configuration/index.md) for details.

```bash
# Use a specific model
ELROY_CHAT_MODEL=claude-sonnet-4-5-20250929 elroy

# Use a custom config file
ELROY_CONFIG_PATH=~/my-elroy-config.yaml elroy
```

## Document Ingestion

To ingest documents into Elroy's memory, use the command palette inside the chat interface or configure background ingestion via the config file:

```yaml
# ~/.elroy/elroy.conf.yaml
background_ingest_enabled: true
background_ingest_paths:
  - ~/documents/
background_ingest_interval_minutes: 60
```
