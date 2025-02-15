# CLI Reference

## Commands

- `elroy chat` - Opens an interactive chat session (default command)
- `elroy message TEXT` - Process a single message and exit
- `elroy remember [TEXT]` - Create a new memory from text or interactively
- `elroy list-models` - Lists supported chat models and exits
- `elroy list-tools` - Lists all available tools
- `elroy print-config` - Shows current configuration and exits
- `elroy version` - Show version and exit
- `elroy print-tool-schemas` - Prints the schema for tools and exits
- `elroy set-persona TEXT` - Set a custom persona for the assistant
- `elroy reset-persona` - Removes any custom persona, reverting to the default
- `elroy show-persona` - Print the system persona and exit
- `elroy mcp` - MCP server commands

Note: Running just `elroy` without any command will default to `elroy chat`.

## Configuration Options

### Basic Configuration
- `--config` - YAML config file path. Values override defaults but are overridden by CLI flags and environment variables
- `--default-assistant-name` - Default name for the assistant
- `--debug` - Enable fail-fast error handling and verbose logging output
- `--user-token` - User token for Elroy
- `--custom-tools-path` - Path to custom functions to load
- `--database-url` - SQLite or Postgres URL for the database (pgvector extension required for Postgres)
- `--inline-tool-calls` - Enable inline tool calls in the assistant (better for some open source models)

### Model Selection
- `--chat-model` - Model for chat completions
- `--chat-model-api-base` - Base URL for OpenAI compatible chat model API
- `--chat-model-api-key` - API key for OpenAI compatible chat model API
- `--embedding-model` - Model for text embeddings
- `--embedding-model-size` - Size of embedding model (default: 1536)
- `--embedding-model-api-base` - Base URL for OpenAI compatible embedding model API
- `--embedding-model-api-key` - API key for OpenAI compatible embedding model API
- `--enable-caching` - Enable caching for LLM (both embeddings and completions)

Quick Model Selection:
- `--sonnet` - Use Anthropic's Sonnet model
- `--opus` - Use Anthropic's Opus model
- `--4o` - Use OpenAI's GPT-4o model
- `--4o-mini` - Use OpenAI's GPT-4o-mini model
- `--o1` - Use OpenAI's o1 model
- `--o1-mini` - Use OpenAI's o1-mini model

### Context Management
- `--max-assistant-loops` - Maximum loops assistant is available to execute in a row (default: 4)
- `--context-refresh-trigger-tokens` - Token threshold for context refresh (default: 10000)
- `--context-refresh-target-tokens` - Target tokens after context refresh (default: 5000)
- `--max-context-age-minutes` - Maximum age in minutes to keep messages in context (default: 720.0)
- `--min-convo-age-for-greeting-minutes` - Minimum conversation age before greeting on login (default: 10.0)
- `--enable-assistant-greeting` - Allow assistant to send first message

### Memory Settings
- `--memories-between-consolidation` - Memories before consolidation (default: 4)
- `--l2-memory-relevance-distance-threshold` - Memory relevance threshold (default: 1.24)
- `--memory-cluster-similarity-threshold` - Cluster similarity threshold (default: 0.21125)
- `--max-memory-cluster-size` - Maximum memories per cluster (default: 5)
- `--min-memory-cluster-size` - Minimum memories per cluster (default: 3)

### UI Configuration
- `--show-internal-thought` - Show assistant's internal thought monologue

### Shell Integration
- `--install-completion` - Install completion for the current shell
- `--show-completion` - Show completion for current shell
- `--help` - Show help message and exit

Note: All configuration options can be set via environment variables with the prefix `ELROY_` (e.g., `ELROY_DEBUG`, `ELROY_CHAT_MODEL`).
