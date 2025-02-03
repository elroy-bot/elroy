# Configuration

Elroy's configuration can be specified in three ways, in order of precedence:

1. Command Line Flags: Highest priority, overrides all other settings
   ```bash
   elroy --chat-model gpt-4o --debug
   ```

2. Environment Variables: Second priority, overridden by CLI flags
   ```bash
   export ELROY_CHAT_MODEL=gpt-4o
   export ELROY_DEBUG=1
   ```

3. Configuration File: Lowest priority, overridden by both CLI flags and environment variables
   ```yaml
   # ~/.config/elroy/config.yaml
   chat_model: gpt-4o
   debug: true
   ```

The configuration file location can be specified with the `--config` flag or defaults to `~/.config/elroy/config.yaml`.

For default config values, see [defaults.yml](../elroy/defaults.yml)

## Customization

You can customize Elroy's appearance with these options:

- `--system-message-color TEXT` - Color for system messages
- `--user-input-color TEXT` - Color for user input
- `--assistant-color TEXT` - Color for assistant output
- `--warning-color TEXT` - Color for warning messages


## Configuration Options

### Basic Configuration
* `--tool TEXT`: Specifies the tool to use in responding to a message. If specified, the assistant MUST use the tool in responding. Only valid when processing a single message.
* `--config TEXT`: Path to YAML configuration file. Values override defaults but are overridden by explicit flags or environment variables.
* `--default-persona TEXT`: Default persona to use for assistants. [env var: ELROY_DEFAULT_PERSONA]
* `--debug / --no-debug`: Whether to fail fast when errors occur, and emit more verbose logging. [env var: ELROY_DEBUG]
* `--user-token TEXT`: User token to use for Elroy [env var: ELROY_USER_TOKEN]

### Database Configuration
* `--database-url TEXT`: Valid SQLite or Postgres URL for the database. If Postgres, the pgvector extension must be installed. [env var: ELROY_DATABASE_URL]

### API Configuration
* `--openai-api-key TEXT`: OpenAI API key, required for OpenAI (or OpenAI compatible) models. [env var: OPENAI_API_KEY]
* `--openai-api-base TEXT`: OpenAI API (or OpenAI compatible) base URL. [env var: OPENAI_API_BASE]
* `--openai-embedding-api-base TEXT`: OpenAI API (or OpenAI compatible) base URL for embeddings. [env var: OPENAI_API_BASE]
* `--openai-organization TEXT`: OpenAI (or OpenAI compatible) organization ID. [env var: OPENAI_ORGANIZATION]
* `--anthropic-api-key TEXT`: Anthropic API key, required for Anthropic models. [env var: ANTHROPIC_API_KEY]

### Model Configuration
* `--chat-model TEXT`: The model to use for chat completions. [env var: ELROY_CHAT_MODEL] [default: (gpt-4o)]
* `--embedding-model TEXT`: The model to use for text embeddings. [env var: ELROY_EMBEDDING_MODEL] [default: text-embedding-3-small]
* `--embedding-model-size INTEGER`: The size of the embedding model. [default: 1536]
* `--enable-caching / --no-enable-caching`: Whether to enable caching for the LLM, both for embeddings and completions. [default: True]
* `--sonnet`: Use Anthropic's Sonnet model
* `--opus`: Use Anthropic's Opus model
* `--4o`: Use OpenAI's GPT-4o model
* `--4o-mini`: Use OpenAI's GPT-4o-mini model
* `--o1`: Use OpenAI's o1 model
* `--o1-mini`: Use OpenAI's o1-mini model

### Context Management
* `--context-refresh-trigger-tokens INTEGER`: Number of tokens that triggers a context refresh and compression of messages in the context window. [default: 3300]
* `--max-assistant-loops INTEGER`: Maximum number of loops the assistant can run before tools are temporarily made unavailable. [default: 4]
* `--context-refresh-target-tokens INTEGER`: Target number of tokens after context refresh / compression, how many tokens to aim to keep in context. [default: 1650]
* `--max-context-age-minutes FLOAT`: Maximum age in minutes to keep. Messages older than this will be dropped from context, regardless of token limits. [default: 120.0]
* `--context-refresh-interval-minutes FLOAT`: How often in minutes to refresh system message and compress context. [default: 10.0]
* `--min-convo-age-for-greeting-minutes FLOAT`: Minimum age in minutes of conversation before the assistant will offer a greeting on login. [default: 10.0]
* `--enable-assistant-greeting / --no-enable-assistant-greeting`: Whether to allow the assistant to send the first message [default: True]

### Memory Management
* `--memories-between-consolidation INTEGER`: How many memories to create before triggering a memory consolidation operation. [default: 4]
* `--l2-memory-relevance-distance-threshold FLOAT`: L2 distance threshold for memory relevance. [default: 1.24]
* `--memory-cluster-similarity-threshold FLOAT`: Threshold for memory cluster similarity. [default: 0.21125]
* `--max-memory-cluster-size INTEGER`: The maximum number of memories that can be consolidated into a single memory at once. [default: 5]
* `--min-memory-cluster-size INTEGER`: The minimum number of memories that can be consolidated into a single memory at once. [default: 3]
* `--initial-context-refresh-wait-seconds INTEGER`: Initial wait time in seconds after login before the initial context refresh and compression. [default: 600]

### UI Configuration
* `--show-internal-thought`: Show the assistant's internal thought monologue. [default: False]
* `--system-message-color TEXT`: Color for system messages. [default: #9ACD32]
* `--user-input-color TEXT`: Color for user input. [default: #FFE377]
* `--assistant-color TEXT`: Color for assistant output. [default: #77DFD8]
* `--warning-color TEXT`: Color for warning messages. [default: yellow]
* `--internal-thought-color TEXT`: Color for internal thought messages. [default: #708090]
