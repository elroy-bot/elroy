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

## Configuration Options

### Basic Configuration
* `--config TEXT`: YAML config file path. Values override defaults but are overridden by CLI flags and environment variables. [env var: ELROY_CONFIG_FILE]
* `--default-assistant-name TEXT`: Default name for the assistant. [env var: ELROY_DEFAULT_ASSISTANT_NAME] [default: Elroy]
* `--debug / --no-debug`: Enable fail-fast error handling and verbose logging output. [env var: ELROY_DEBUG] [default: false]
* `--user-token TEXT`: User token to use for Elroy. [env var: ELROY_USER_TOKEN] [default: DEFAULT]
* `--custom-tools-path TEXT`: Path to custom functions to load (can be specified multiple times)
* `--database-url TEXT`: Valid SQLite or Postgres URL for the database. If Postgres, the pgvector extension must be installed. [env var: ELROY_DATABASE_URL]
* `--inline-tool-calls / --no-inline-tool-calls`: Whether to enable inline tool calls in the assistant (better for some open source models). [env var: ELROY_INLINE_TOOL_CALLS] [default: false]

### Model Selection and Configuration
Elroy will automatically select appropriate models based on available API keys:
- With ANTHROPIC_API_KEY: Uses Claude 3 Sonnet (claude-3-5-sonnet-20241022)
- With OPENAI_API_KEY: Uses GPT-4o (gpt-4o) and text-embedding-3-small
- With GEMINI_API_KEY: Uses Gemini 2.0 Flash (gemini/gemini-2.0-flash)

Model configuration options:
* `--chat-model TEXT`: The model to use for chat completions. [env var: ELROY_CHAT_MODEL]
* `--chat-model-api-base TEXT`: Base URL for OpenAI compatible chat model API. Litellm will recognize vars too. [env var: ELROY_CHAT_MODEL_API_BASE]
* `--chat-model-api-key TEXT`: API key for OpenAI compatible chat model API. [env var: ELROY_CHAT_MODEL_API_KEY]
* `--embedding-model TEXT`: The model to use for text embeddings. [env var: ELROY_EMBEDDING_MODEL] [default: text-embedding-3-small]
* `--embedding-model-size INTEGER`: The size of the embedding model. [env var: ELROY_EMBEDDING_MODEL_SIZE] [default: 1536]
* `--embedding-model-api-base TEXT`: Base URL for OpenAI compatible embedding model API. [env var: ELROY_EMBEDDING_MODEL_API_BASE]
* `--embedding-model-api-key TEXT`: API key for OpenAI compatible embedding model API. [env var: ELROY_EMBEDDING_MODEL_API_KEY]
* `--enable-caching / --no-enable-caching`: Whether to enable caching for the LLM. [env var: ELROY_ENABLE_CACHING] [default: true]

Model Aliases:
* `--sonnet`: Use Anthropic's Claude 3 Sonnet model
* `--opus`: Use Anthropic's Claude 3 Opus model
* `--4o`: Use OpenAI's GPT-4o model
* `--4o-mini`: Use OpenAI's GPT-4o-mini model
* `--o1`: Use OpenAI's o1 model
* `--o1-mini`: Use OpenAI's o1-mini model

### Context Management
* `--max-assistant-loops INTEGER`: Maximum number of loops the assistant can run before tools are temporarily made unvailable. [env var: ELROY_MAX_ASSISTANT_LOOPS] [default: 4]
* `--max-tokens INTEGER`: Number of tokens that triggers a context refresh and compresion of messages in the context window. [env var: ELROY_MAX_TOKENS] [default: 10000]
* `--max-context-age-minutes FLOAT`: Maximum age in minutes to keep messages in context. [env var: ELROY_MAX_CONTEXT_AGE_MINUTES] [default: 720.0]
* `--min-convo-age-for-greeting-minutes FLOAT`: Minimum age in minutes of conversation before the assistant will offer a greeting on login. 0 means assistant will offer greeting each time. To disable greeting, set --first=True. [env var: ELROY_MIN_CONVO_AGE_FOR_GREETING_MINUTES] [default: 10.0]

### Memory Consolidation
* `--memories-between-consolidation INTEGER`: Memories before consolidation. [env var: ELROY_MEMORIES_BETWEEN_CONSOLIDATION] [default: 4]
* `--l2-memory-relevance-distance-threshold FLOAT`: L2 distance threshold. [env var: ELROY_L2_MEMORY_RELEVANCE_DISTANCE_THRESHOLD] [default: 1.24]
* `--memory-cluster-similarity-threshold FLOAT`: Cluster similarity threshold. The lower parameter is, the less likely memories are to be consolidated. [env var: ELROY_MEMORY_CLUSTER_SIMILARITY_THRESHOLD] [default: 0.21125]
* `--max-memory-cluster-size INTEGER`: Maximum memories per consolidation. [env var: ELROY_MAX_MEMORY_CLUSTER_SIZE] [default: 5]
* `--min-memory-cluster-size INTEGER`: Minimum memories per consolidation. [env var: ELROY_MIN_MEMORY_CLUSTER_SIZE] [default: 3]

### UI Configuration
* `--show-internal-thought / --no-show-internal-thought`: Show internal thought monologue. [env var: ELROY_SHOW_INTERNAL_THOUGHT] [default: true]
* `--system-message-color TEXT`: System message color. [env var: ELROY_SYSTEM_MESSAGE_COLOR] [default: #9ACD32]
* `--user-input-color TEXT`: User input color. [env var: ELROY_USER_INPUT_COLOR] [default: #FFE377]
* `--assistant-color TEXT`: Assistant output color. [env var: ELROY_ASSISTANT_COLOR] [default: #77DFD8]
* `--warning-color TEXT`: Warning message color. [env var: ELROY_WARNING_COLOR] [default: yellow]
* `--internal-thought-color TEXT`: Internal thought color. [env var: ELROY_INTERNAL_THOUGHT_COLOR] [default: #708090]
