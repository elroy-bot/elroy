# CLI Reference

## Commands

- `elroy chat` - Opens an interactive chat session (default command)
- `elroy message TEXT` - Process a single message and exit
- `elroy remember [TEXT]` - Create a new memory from text or interactively
- `elroy list-models` - Lists supported chat models and exits
- `elroy list-tools` - Lists all available tools
- `elroy print-config` - Shows current configuration and exits
- `elroy version` - Show version and exit
- `elroy print-tool-schemas` - Prints the schema for a tool and exits
- `elroy mcp` - MCP server commands

Note: Running just `elroy` without any command will default to `elroy chat`.

## Configuration Options

### Basic Configuration
- `--config` - YAML config file path. Values override defaults but are overridden by CLI flags and environment variables
- `--default-assistant-name` - Default name for the assistant (default: Elroy)
- `--debug` - Enable fail-fast error handling and verbose logging output
- `--user-token` - User token for Elroy (default: DEFAULT)
- `--custom-tools-path` - Path to custom functions to load
- `--database-url` - SQLite or Postgres URL for the database (pgvector extension required for Postgres)
- `--inline-tool-calls` - Enable inline tool calls in the assistant (better for some open source models)

### Model Selection
- `--chat-model` - Model for chat completions
- `--chat-model-api-base` - Base URL for OpenAI compatible chat model API (Litellm compatible)
- `--chat-model-api-key` - API key for OpenAI compatible chat model API
- `--embedding-model` - Model for text embeddings (default: text-embedding-3-small)
- `--embedding-model-size` - Size of embedding model (default: 1536)
- `--embedding-model-api-base` - Base URL for OpenAI compatible embedding model API
- `--embedding-model-api-key` - API key for OpenAI compatible embedding model API
- `--enable-caching` - Enable caching for LLM (both embeddings and completions, default: true)

Quick Model Selection:
- `--sonnet` - Use Anthropic's Sonnet model
- `--opus` - Use Anthropic's Opus model
- `--4o` - Use OpenAI's GPT-4o model
- `--4o-mini` - Use OpenAI's GPT-4o-mini model
- `--o1` - Use OpenAI's o1 model
- `--o1-mini` - Use OpenAI's o1-mini model

### Context Management
- `--max-assistant-loops` - Maximum loops assistant can run before tools are temporarily unavailable (default: 4)
- `--max-tokens` - Number of tokens that triggers a context refresh (default: 10000)
- `--max-context-age-minutes` - Maximum age in minutes to keep messages in context (default: 720.0)
- `--min-convo-age-for-greeting-minutes` - Minimum conversation age before greeting on login (default: 120.0)
- `--first` - If true, assistant will not send the first message

### Memory Management
- `--memories-between-consolidation` - Memories before consolidation (default: 4)
- `--l2-memory-relevance-distance-threshold` - Memory relevance threshold (default: 1.24)
- `--memory-cluster-similarity-threshold` - Cluster similarity threshold (default: 0.21125)
- `--max-memory-cluster-size` - Maximum memories per cluster (default: 5)
- `--min-memory-cluster-size` - Minimum memories per cluster (default: 3)

### UI Configuration
- `--show-internal-thought` - Show assistant's internal thought monologue (default: true)

### Shell Integration
- `--install-completion` - Install completion for the current shell
- `--show-completion` - Show completion for current shell
- `--help` - Show help message and exit

Note: All configuration options can be set via environment variables with the prefix `ELROY_` (e.g., `ELROY_CHAT_MODEL`).
