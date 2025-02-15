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
- `--config` - YAML config file path
- `--default-assistant-name` - Default name for the assistant
- `--debug` - Enable fail-fast error handling and verbose logging
- `--user-token` - User token for Elroy
- `--custom-tools-path` - Path to custom functions
- `--database-url` - SQLite or Postgres URL for the database
- `--inline-tool-calls` - Enable inline tool calls in the assistant

### Model Selection
- `--chat-model` - Model for chat completions
- `--chat-model-api-base` - Base URL for chat model API
- `--chat-model-api-key` - API key for chat model
- `--embedding-model` - Model for text embeddings
- `--embedding-model-size` - Size of embedding model
- `--embedding-model-api-base` - Base URL for embedding model API
- `--embedding-model-api-key` - API key for embedding model
- `--enable-caching` - Enable LLM caching

Quick Model Selection:
- `--sonnet` - Use Anthropic's Sonnet model
- `--opus` - Use Anthropic's Opus model
- `--4o` - Use OpenAI's GPT-4o model
- `--4o-mini` - Use OpenAI's GPT-4o-mini model
- `--o1` - Use OpenAI's o1 model
- `--o1-mini` - Use OpenAI's o1-mini model

### Context Management
- `--max-assistant-loops` - Maximum loops before tool timeout
- `--context-refresh-trigger-tokens` - Token threshold for context refresh
- `--context-refresh-target-tokens` - Target tokens after refresh
- `--max-context-age-minutes` - Maximum age to keep messages
- `--min-convo-age-for-greeting-minutes` - Minimum age before greeting
- `--enable-assistant-greeting` - Allow assistant first message

### Memory Settings
- `--memories-between-consolidation` - Memories before consolidation
- `--l2-memory-relevance-distance-threshold` - Memory relevance threshold
- `--memory-cluster-similarity-threshold` - Cluster similarity threshold
- `--max-memory-cluster-size` - Maximum memories per cluster
- `--min-memory-cluster-size` - Minimum memories per cluster

### UI Configuration
- `--show-internal-thought` - Show assistant's internal thoughts

### Shell Integration
- `--install-completion` - Install shell completion
- `--show-completion` - Show completion for current shell
- `--help` - Show help message and exit
