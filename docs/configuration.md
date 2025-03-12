# Configuration

## Configuration Methods

Elroy's configuration can be specified in three ways, in order of precedence:

1. **Command Line Flags**: Highest priority, overrides all other settings
2. **Environment Variables**: Second priority, overridden by CLI flags
3. **Configuration File**: Lowest priority, overridden by both CLI flags and environment variables

The configuration file location can be specified with the `--config` flag or defaults to `~/.config/elroy/config.yaml`.

For default config values, see [defaults.yml](https://github.com/elroy-bot/elroy/blob/main/elroy/defaults.yml)

## Parameter Naming Conventions

Each configuration parameter can be specified in three different formats:

| Format | Example | Usage |
|--------|---------|-------|
| CLI Flag | `--chat-model` | Used with the command line interface |
| Environment Variable | `ELROY_CHAT_MODEL` | Used when setting environment variables |
| Config File | `chat_model` | Used in the YAML configuration file |

**Conversion Rules:**
- **CLI Flag to Environment Variable**: Remove leading dashes, convert to uppercase, and add `ELROY_` prefix
  - Example: `--chat-model` → `ELROY_CHAT_MODEL`
- **CLI Flag to Config File**: Remove leading dashes
  - Example: `--chat-model` → `chat_model`

**Examples:**

```bash
# Command line flag
elroy --chat-model claude-3-5-sonnet-20241022

# Environment variable
export ELROY_CHAT_MODEL=gpt-4o
export ELROY_DEBUG=1

# Configuration file (config.yaml)
chat_model: gpt-4o
debug: true
```

## Commands

| Command | Description |
|---------|-------------|
| `elroy chat` | Opens an interactive chat session (default command) |
| `elroy message TEXT` | Process a single message and exit |
| `elroy remember [TEXT]` | Create a new memory from text or interactively |
| `elroy list-models` | Lists supported chat models and exits |
| `elroy list-tools` | Lists all available tools |
| `elroy print-config` | Shows current configuration and exits |
| `elroy version` | Show version and exit |
| `elroy print-tool-schemas` | Prints the schema for a tool and exits |
| `elroy set-persona TEXT` | Set a custom persona for the assistant |
| `elroy reset-persona` | Removes any custom persona, reverting to the default |
| `elroy show-persona` | Print the system persona and exit |
| `elroy mcp` | MCP server commands |

Note: Running just `elroy` without any command will default to `elroy chat`.

## Configuration Options

### Basic Configuration

| CLI Flag | Environment Variable | Config File | Type | Description | Default |
|----------|---------------------|-------------|------|-------------|---------|
| `--config` | `ELROY_CONFIG` | N/A | TEXT | YAML config file path | `~/.config/elroy/config.yaml` |
| `--default-assistant-name` | `ELROY_DEFAULT_ASSISTANT_NAME` | `default_assistant_name` | TEXT | Default name for the assistant | `Elroy` |
| `--debug` / `--no-debug` | `ELROY_DEBUG` | `debug` | BOOLEAN | Enable fail-fast error handling and verbose logging | `false` |
| `--user-token` | `ELROY_USER_TOKEN` | `user_token` | TEXT | User token to use for Elroy | `DEFAULT` |
| `--custom-tools-path` | `ELROY_CUSTOM_TOOLS_PATH` | `custom_tools_path` | TEXT | Path to custom functions to load (can be specified multiple times) | - |
| `--max-ingested-doc-lines` | `ELROY_MAX_INGESTED_DOC_LINES` | `max_ingested_doc_lines` | INTEGER | Maximum number of lines to ingest from a document | - |
| `--database-url` | `ELROY_DATABASE_URL` | `database_url` | TEXT | Valid SQLite or Postgres URL for the database | - |
| `--inline-tool-calls` / `--no-inline-tool-calls` | `ELROY_INLINE_TOOL_CALLS` | `inline_tool_calls` | BOOLEAN | Enable inline tool calls in the assistant | `false` |

### Model Selection and Configuration

#### Automatic Model Selection
Elroy will automatically select appropriate models based on available API keys:

| API Key | Chat Model | Embedding Model |
|---------|------------|----------------|
| `ANTHROPIC_API_KEY` | Claude 3 Sonnet | text-embedding-3-small |
| `OPENAI_API_KEY` | GPT-4o | text-embedding-3-small |
| `GEMINI_API_KEY` | Gemini 2.0 Flash | text-embedding-3-small |

#### Model Configuration Options

| CLI Flag | Environment Variable | Config File | Type | Description | Default |
|----------|---------------------|-------------|------|-------------|---------|
| `--chat-model` | `ELROY_CHAT_MODEL` | `chat_model` | TEXT | Model to use for chat completions | *Inferred from API keys* |
| `--chat-model-api-base` | `ELROY_CHAT_MODEL_API_BASE` | `chat_model_api_base` | TEXT | Base URL for OpenAI compatible chat model API | - |
| `--chat-model-api-key` | `ELROY_CHAT_MODEL_API_KEY` | `chat_model_api_key` | TEXT | API key for OpenAI compatible chat model API | - |
| `--embedding-model` | `ELROY_EMBEDDING_MODEL` | `embedding_model` | TEXT | Model to use for text embeddings | `text-embedding-3-small` |
| `--embedding-model-size` | `ELROY_EMBEDDING_MODEL_SIZE` | `embedding_model_size` | INTEGER | Size of the embedding model | `1536` |
| `--embedding-model-api-base` | `ELROY_EMBEDDING_MODEL_API_BASE` | `embedding_model_api_base` | TEXT | Base URL for OpenAI compatible embedding model API | - |
| `--embedding-model-api-key` | `ELROY_EMBEDDING_MODEL_API_KEY` | `embedding_model_api_key` | TEXT | API key for OpenAI compatible embedding model API | - |
| `--enable-caching` / `--no-enable-caching` | `ELROY_ENABLE_CACHING` | `enable_caching` | BOOLEAN | Enable caching for the LLM | `true` |

#### Model Aliases
Shortcuts for common models:

| CLI Flag | Description |
|----------|-------------|
| `--sonnet` | Use Anthropic's Claude 3 Sonnet model |
| `--opus` | Use Anthropic's Claude 3 Opus model |
| `--4o` | Use OpenAI's GPT-4o model |
| `--4o-mini` | Use OpenAI's GPT-4o-mini model |
| `--o1` | Use OpenAI's o1 model |
| `--o1-mini` | Use OpenAI's o1-mini model |

### Context Management

| CLI Flag | Environment Variable | Config File | Type | Description | Default |
|----------|---------------------|-------------|------|-------------|---------|
| `--max-assistant-loops` | `ELROY_MAX_ASSISTANT_LOOPS` | `max_assistant_loops` | INTEGER | Maximum number of loops before tools are temporarily unavailable | `4` |
| `--max-tokens` | `ELROY_MAX_TOKENS` | `max_tokens` | INTEGER | Number of tokens that triggers a context refresh | `10000` |
| `--max-context-age-minutes` | `ELROY_MAX_CONTEXT_AGE_MINUTES` | `max_context_age_minutes` | FLOAT | Maximum age in minutes to keep messages in context | `720` |
| `--min-convo-age-for-greeting-minutes` | `ELROY_MIN_CONVO_AGE_FOR_GREETING_MINUTES` | `min_convo_age_for_greeting_minutes` | FLOAT | Minimum age in minutes before offering a greeting on login | `120` |
| `--first` | `ELROY_FIRST` | `first` | BOOLEAN | If true, assistant will not send the first message | `false` |

### Memory Consolidation

| CLI Flag | Environment Variable | Config File | Type | Description | Default |
|----------|---------------------|-------------|------|-------------|---------|
| `--memories-between-consolidation` | `ELROY_MEMORIES_BETWEEN_CONSOLIDATION` | `memories_between_consolidation` | INTEGER | How many memories before triggering consolidation | `4` |
| `--l2-memory-relevance-distance-threshold` | `ELROY_L2_MEMORY_RELEVANCE_DISTANCE_THRESHOLD` | `l2_memory_relevance_distance_threshold` | FLOAT | L2 distance threshold for memory relevance | `1.24` |
| `--memory-cluster-similarity-threshold` | `ELROY_MEMORY_CLUSTER_SIMILARITY_THRESHOLD` | `memory_cluster_similarity_threshold` | FLOAT | Threshold for memory cluster similarity | `0.21125` |
| `--max-memory-cluster-size` | `ELROY_MAX_MEMORY_CLUSTER_SIZE` | `max_memory_cluster_size` | INTEGER | Maximum number of memories to consolidate at once | `5` |
| `--min-memory-cluster-size` | `ELROY_MIN_MEMORY_CLUSTER_SIZE` | `min_memory_cluster_size` | INTEGER | Minimum number of memories to consolidate at once | `3` |

### UI Configuration

| CLI Flag | Environment Variable | Config File | Type | Description | Default |
|----------|---------------------|-------------|------|-------------|---------|
| `--show-internal-thought` / `--no-show-internal-thought` | `ELROY_SHOW_INTERNAL_THOUGHT` | `show_internal_thought` | BOOLEAN | Show the assistant's internal thought monologue | `true` |
| `--system-message-color` | `ELROY_SYSTEM_MESSAGE_COLOR` | `system_message_color` | TEXT | Color for system messages | `#9ACD32` |
| `--user-input-color` | `ELROY_USER_INPUT_COLOR` | `user_input_color` | TEXT | Color for user input | `#FFE377` |
| `--assistant-color` | `ELROY_ASSISTANT_COLOR` | `assistant_color` | TEXT | Color for assistant output | `#77DFD8` |
| `--warning-color` | `ELROY_WARNING_COLOR` | `warning_color` | TEXT | Color for warning messages | `yellow` |
| `--internal-thought-color` | `ELROY_INTERNAL_THOUGHT_COLOR` | `internal_thought_color` | TEXT | Color for internal thought messages | `#708090` |

### Shell Integration

| CLI Flag | Description |
|----------|-------------|
| `--install-completion` | Install completion for the current shell |
| `--show-completion` | Show completion for current shell |
| `--help` | Show help message and exit |
