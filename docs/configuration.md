# Configuration

## Configuration Methods

Elroy's configuration can be specified in three ways, in order of precedence:

1. **Command Line Flags**: Highest priority, overrides all other settings
   ```bash
   elroy --chat-model claude-3-5-sonnet-20241022
   ```

2. **Environment Variables**: Second priority, overridden by CLI flags. All environment variables are prefixed with `ELROY_` and use uppercase with underscores:
   ```bash
   export ELROY_CHAT_MODEL=gpt-4o
   export ELROY_DEBUG=1
   ```

3. **Configuration File**: Lowest priority, overridden by both CLI flags and environment variables
   ```yaml
   # ~/.config/elroy/config.yaml
   chat_model: gpt-4o
   debug: true
   ```

The configuration file location can be specified with the `--config` flag or defaults to `~/.config/elroy/config.yaml`.

For default config values, see [defaults.yml](https://github.com/elroy-bot/elroy/blob/main/elroy/defaults.yml)

## Commands

- `elroy chat` - Opens an interactive chat session (default command)
- `elroy message TEXT` - Process a single message and exit
- `elroy remember [TEXT]` - Create a new memory from text or interactively
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

## Configuration Options

> **Note:** All configuration options can be set via environment variables with the prefix `ELROY_` (e.g.,`ELROY_CHAT_MODEL=gpt-4o`). The environment variable name is created by converting the option name to uppercase and adding the `ELROY_` prefix.

### Basic Configuration
* `--config TEXT`: YAML config file path. Values override defaults but are overridden by CLI flags and environment variables. [default: ~/.config/elroy/config.yaml]
* `--default-assistant-name TEXT`: Default name for the assistant. [default: Elroy]
* `--debug / --no-debug`: Enable fail-fast error handling and verbose logging output. [default: false]
* `--user-token TEXT`: User token to use for Elroy. [default: DEFAULT]
* `--custom-tools-path TEXT`: Path to custom functions to load (can be specified multiple times)
* `--max-ingested-doc-lines INTEGER`: Maximum number of lines to ingest from a document. If a document has more lines, it will be ignored.
* `--database-url TEXT`: Valid SQLite or Postgres URL for the database. If Postgres, the pgvector extension must be installed.
* `--inline-tool-calls / --no-inline-tool-calls`: Whether to enable inline tool calls in the assistant (better for some open source models). [default: false]

### Model Selection and Configuration

#### Automatic Model Selection
Elroy will automatically select appropriate models based on available API keys:

| API Key | Chat Model | Embedding Model |
|---------|------------|----------------|
| `ANTHROPIC_API_KEY` | Claude 3 Sonnet | text-embedding-3-small |
| `OPENAI_API_KEY` | GPT-4o | text-embedding-3-small |
| `GEMINI_API_KEY` | Gemini 2.0 Flash | text-embedding-3-small |

#### Model Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--chat-model TEXT` | The model to use for chat completions | *Inferred from API keys* |
| `--chat-model-api-base TEXT` | Base URL for OpenAI compatible chat model API | - |
| `--chat-model-api-key TEXT` | API key for OpenAI compatible chat model API | - |
| `--embedding-model TEXT` | The model to use for text embeddings | text-embedding-3-small |
| `--embedding-model-size INTEGER` | The size of the embedding model | 1536 |
| `--embedding-model-api-base TEXT` | Base URL for OpenAI compatible embedding model API | - |
| `--embedding-model-api-key TEXT` | API key for OpenAI compatible embedding model API | - |
| `--enable-caching / --no-enable-caching` | Whether to enable caching for the LLM | true |

#### Model Aliases
Shortcuts for common models:

| Alias | Description |
|-------|-------------|
| `--sonnet` | Use Anthropic's Claude 3 Sonnet model |
| `--opus` | Use Anthropic's Claude 3 Opus model |
| `--4o` | Use OpenAI's GPT-4o model |
| `--4o-mini` | Use OpenAI's GPT-4o-mini model |
| `--o1` | Use OpenAI's o1 model |
| `--o1-mini` | Use OpenAI's o1-mini model |

### Context Management
* `--max-assistant-loops INTEGER`: Maximum number of loops the assistant can run before tools are temporarily made unavailable (returning for the next user message). [default: 4]
* `--max-tokens INTEGER`: Number of tokens that triggers a context refresh and compression of messages in the context window. [default: 10000]
* `--max-context-age-minutes FLOAT`: Maximum age in minutes to keep. Messages older than this will be dropped from context, regardless of token limits. [default: 720]
* `--min-convo-age-for-greeting-minutes FLOAT`: Minimum age in minutes of conversation before the assistant will offer a greeting on login. 0 means assistant will offer greeting each time. To disable greeting, set --first=True (This will override any value for min_convo_age_for_greeting_minutes). [default: 120]
* `--first`: If true, assistant will not send the first message.

### Memory Consolidation
* `--memories-between-consolidation INTEGER`: How many memories to create before triggering a memory consolidation operation. [default: 4]
* `--l2-memory-relevance-distance-threshold FLOAT`: L2 distance threshold for memory relevance. [default: 1.24]
* `--memory-cluster-similarity-threshold FLOAT`: Threshold for memory cluster similarity. The lower the parameter is, the less likely memories are to be consolidated. [default: 0.21125]
* `--max-memory-cluster-size INTEGER`: The maximum number of memories that can be consolidated into a single memory at once. [default: 5]
* `--min-memory-cluster-size INTEGER`: The minimum number of memories that can be consolidated into a single memory at once. [default: 3]

### UI Configuration
* `--show-internal-thought / --no-show-internal-thought`: Show the assistant's internal thought monologue. [default: true]
* `--system-message-color TEXT`: Color for system messages. [default: #9ACD32]
* `--user-input-color TEXT`: Color for user input. [default: #FFE377]
* `--assistant-color TEXT`: Color for assistant output. [default: #77DFD8]
* `--warning-color TEXT`: Color for warning messages. [default: yellow]
* `--internal-thought-color TEXT`: Color for internal thought messages. [default: #708090]

### Shell Integration
* `--install-completion`: Install completion for the current shell
* `--show-completion`: Show completion for current shell
* `--help`: Show help message and exit
