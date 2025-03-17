# Basic Configuration

These settings control the core behavior of Elroy.

## Options

* `--config TEXT`: YAML config file path. Values override defaults but are overridden by CLI flags and environment variables. [default: ~/.config/elroy/config.yaml]
* `--default-assistant-name TEXT`: Default name for the assistant. [default: Elroy]
* `--debug / --no-debug`: Enable fail-fast error handling and verbose logging output. [default: false]
* `--user-token TEXT`: User token to use for Elroy. [default: DEFAULT]
* `--custom-tools-path TEXT`: Path to custom functions to load (can be specified multiple times)
* `--max-ingested-doc-lines INTEGER`: Maximum number of lines to ingest from a document. If a document has more lines, it will be ignored.
* `--database-url TEXT`: Valid SQLite or Postgres URL for the database. If Postgres, the pgvector extension must be installed.
* `--inline-tool-calls / --no-inline-tool-calls`: Whether to enable inline tool calls in the assistant (better for some open source models). [default: false]
* `--reflect / --no-reflect`: If true, the assistant will reflect on memories it recalls. This will lead to slower but richer responses. If false, memories will be less processed when recalled into memory. [default: false]

## Shell Integration

* `--install-completion`: Install completion for the current shell
* `--show-completion`: Show completion for current shell
* `--help`: Show help message and exit

## CLI Commands

- `elroy chat` - Opens an interactive chat session (default command)
- `elroy message TEXT` - Process a single message and exit
- `elroy remember [TEXT]` - Create a new memory from text or interactively
- `elroy ingest PATH` - Ingests document(s) at the given path into memory
- `elroy list-models` - Lists supported chat models and exits
- `elroy list-tools` - Lists all available tools
- `elroy print-config` - Shows current configuration and exits
- `elroy version` - Show version and exit
- `elroy print-tool-schemas` - Prints the schema for a tool and exits
- `elroy set-persona TEXT` - Set a custom persona for the assistant
- `elroy reset-persona` - Removes any custom persona, reverting to the default
- `elroy show-persona` - Print the system persona and exit
- `elroy mcp` - MCP server commands

Note: Running just `elroy` without any command will default to `elroy chat`.
