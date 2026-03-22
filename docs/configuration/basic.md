# Basic Configuration

These settings control the core behavior of Elroy. All options can be set via environment variables (e.g. `ELROY_DEBUG=true`) or in the config file at `~/.elroy/elroy.conf.yaml`.

## Options

| Config Key | Env Variable | Default | Description |
|---|---|---|---|
| `config_path` | `ELROY_CONFIG_PATH` | `~/.elroy/elroy.conf.yaml` | YAML config file path |
| `default_assistant_name` | `ELROY_DEFAULT_ASSISTANT_NAME` | `Elroy` | Default name for the assistant |
| `debug` | `ELROY_DEBUG` | `false` | Enable fail-fast error handling and verbose logging output |
| `user_token` | `ELROY_USER_TOKEN` | `DEFAULT` | User token to use for Elroy |
| `custom_tools_path` | `ELROY_CUSTOM_TOOLS_PATH` | - | Path to custom functions to load |
| `database_url` | `ELROY_DATABASE_URL` | SQLite at `~/.elroy/elroy.db` | Valid SQLite URL for the database |
| `inline_tool_calls` | `ELROY_INLINE_TOOL_CALLS` | `false` | Whether to enable inline tool calls (better for some open source models) |
| `reflect` | `ELROY_REFLECT` | `false` | If true, the assistant will reflect on memories it recalls. Slower but richer responses. |
| `max_ingested_doc_lines` | `ELROY_MAX_INGESTED_DOC_LINES` | `1000` | Maximum number of lines to ingest from a document |

## Example Config File

```yaml
# ~/.elroy/elroy.conf.yaml
default_assistant_name: "Elroy"
debug: false
user_token: DEFAULT
chat_model: claude-sonnet-4-5-20250929
reflect: false
```
