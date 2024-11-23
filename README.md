# Elroy

Elroy is a CLI AI personal assistant with long term memory and goal tracking capabilities. It features:

- **Long-term Memory**: Elroy maintains memories across conversations
- **Goal Tracking**: Track and manage personal/professional goals
- **Memory Panel**: Shows relevant memories during conversations

![Goals Demo](images/goals_demo.gif)


## Installation & Usage

### Option 1: Using Docker (Recommended)

#### Prerequisites
- Docker and Docker Compose
- Relevant API keys (for simplest setup, set OPENAI_API_KEY)

This option automatically sets up everything you need, including the required PostgreSQL database with pgvector extension.

1. Download the docker-compose.yml:
```bash
curl -O https://raw.githubusercontent.com/elroy-bot/elroy/main/docker-compose.yml
```

2. Run Elroy:
```bash
docker compose run --rm elroy
```

The Docker image is publicly available at `ghcr.io/elroy-bot/elroy`.

### Option 2: Using pip

#### Prerequisites
- Python 3.9 or higher
- Relevant API keys (for simplest setup, set OPENAI_API_KEY)
- PostgreSQL database with pgvector extension

```bash
pip install elroy
```

For the database, either:
- Let Elroy manage PostgreSQL via Docker (default) (requires Docker)
- Provide a PostgreSQL connection string, either by setting the `ELROY_POSTGRES_URL` environment variable, or by using the `--postgres_url` flag.

### Option 3: Installing from Source

#### Prerequisites
- Python 3.11 or higher
- Poetry package manager
- Relevant API keys (for simplest setup, set OPENAI_API_KEY)
- PostgreSQL database with pgvector extension

```bash
# Clone the repository
git clone https://github.com/elroy-bot/elroy.git
cd elroy

# Install dependencies and the package
poetry install

# Run Elroy
poetry run elroy
```

For the database, you have the same options as with pip installation:
- Let Elroy manage PostgreSQL via Docker (default)
- Provide your own PostgreSQL connection string

### Basic Usage

Once installed locally you can:
```bash
# Start the chat interface
elroy chat

# Or just 'elroy' which defaults to chat mode
elroy

# Elroy also accepts stdin
echo "Say hello world" | elroy
```

## Available Commands
![Remember command](images/remember_command.gif)

Elroy provides both CLI commands and in-chat commands (which can be used by both users and the assistant). For full schema information, see [tools schema reference](docs/tools_schema.md).

### Model Support

Elroy supports both OpenAI and Anthropic language models:

#### Chat Models
- OpenAI Models: All chat completion models (gpt-3.5-turbo, gpt-4, etc.)
- Anthropic Models: All Claude models (claude-2, claude-instant-1, etc.)
- OpenAI-Compatible APIs: Any provider offering an OpenAI-compatible API endpoint (via --openai-api-base)

#### Embedding Models
- OpenAI Models: text-embedding-ada-002 (default)
- OpenAI-Compatible APIs: Any provider offering OpenAI-compatible embedding endpoints (via --openai-embedding-api-base)

Note: The embedding model size can be configured using the --embedding-model-size flag (default is 1536 for OpenAI models).

Note: For full model compatibility and configuration options, use `elroy list-chat-models` to see all supported chat models and `elroy show-config` to view your current model settings.

Note: For OpenAI models, you'll need an OpenAI API key. For Anthropic models, you'll need an Anthropic API key. You can use compatible API providers by configuring the appropriate base URLs.

Use `elroy list-chat-models` to see all supported chat models.

### CLI Commands
These commands can be run directly from your terminal:

- `elroy chat` - Start the interactive chat interface (default command)
- `elroy remember [--file FILE]` - Create a new memory from stdin, file, or interactively
- `elroy list-chat-models` - List all supported chat models
- `elroy show-config` - Display current configuration settings
- `elroy --version` - Show version information and exit
- `elroy --help` - Show help information and all available options

Note: Running just `elroy` without any command will default to `elroy chat`.

The chat interface accepts input from stdin, so you can pipe text to Elroy:
```bash
echo "What is 2+2?" | elroy chat
```

### In-Chat Commands
While chatting with Elroy, commands can be used by typing a forward slash (/) followed by the command name. Commands are divided into two categories:

#### User-Only Commands
These commands can only be used by human users:

- `/print_available_commands` - Show all available commands
- `/print_system_instruction` - View current system instructions
- `/refresh_system_instructions` - Refresh system instructions
- `/reset_system_context` - Reset conversation context
- `/print_context_messages` - View current conversation context
- `/add_internal_thought` - Insert an internal thought for the assistant
- `/exit` - Exit the chat

#### Assistant and User Commands
These commands can be used by both users and Elroy:

##### Goal Management
- `/create_goal` - Create a new goal
- `/rename_goal` - Rename an existing goal
- `/print_goal` - View details of a specific goal
- `/add_goal_to_current_context` - Add a goal to current conversation
- `/drop_goal_from_current_context` - Remove goal from current conversation
- `/add_goal_status_update` - Update goal progress
- `/mark_goal_completed` - Mark a goal as complete
- `/delete_goal_permanently` - Delete a goal
- `/get_active_goal_names` - List all active goals

##### Memory Management
- `/create_memory` - Create a new memory from text
- `/print_memory` - View a specific memory
- `/add_memory_to_current_context` - Add a memory to current conversation
- `/drop_memory_from_current_context` - Remove memory from current conversation
- `/contemplate [prompt]` - Ask Elroy to reflect on the conversation or a specific topic

##### User Preferences
- `/get_user_full_name` - Get your full name
- `/set_user_full_name` - Set your full name
- `/get_user_preferred_name` - Get your preferred name
- `/set_user_preferred_name` - Set your preferred name

##### Development Tools
- `/start_aider_session [file_location] [comment]` - Start an aider coding session (experimental)
- `/tail_elroy_logs` - View Elroy's log output
- `/print_elroy_config` - Display current configuration
- `/create_bug_report` - Create a bug report with current context

Note: All these commands can be used with a leading slash (/) in the chat interface. The assistant uses these commands without the slash when helping you.


## Customization

You can customize Elroy's appearance with these options:

- `--system-message-color TEXT` - Color for system messages
- `--user-input-color TEXT` - Color for user input
- `--assistant-color TEXT` - Color for assistant output
- `--warning-color TEXT` - Color for warning messages



## Configuration Options

### Basic Configuration
* `--config TEXT`: Path to YAML configuration file. Values override defaults but are overridden by explicit flags or environment variables.
* `--version`: Show version and exit.
* `--debug`: Whether to fail fast when errors occur, and emit more verbose logging.

### Database Configuration
* `--postgres-url TEXT`: Postgres URL to use for Elroy. If set, overrides use_docker_postgres. [env var: ELROY_POSTGRES_URL]
* `--use-docker-postgres / --no-use-docker-postgres`: If true and postgres_url is not set, will attempt to start a Docker container for Postgres. [env var: USE_DOCKER_POSTGRES]
* `--stop-docker-postgres-on-exit / --no-stop-docker-postgres-on-exit`: Whether to stop the Postgres container on exit. [env var: STOP_DOCKER_POSTGRES_ON_EXIT]

### API Configuration
* `--openai-api-key TEXT`: OpenAI API key, required for OpenAI (or OpenAI compatible) models. [env var: OPENAI_API_KEY]
* `--openai-api-base TEXT`: OpenAI API (or OpenAI compatible) base URL. [env var: OPENAI_API_BASE]
* `--openai-embedding-api-base TEXT`: OpenAI API (or OpenAI compatible) base URL for embeddings. [env var: OPENAI_API_BASE]
* `--openai-organization TEXT`: OpenAI (or OpenAI compatible) organization ID. [env var: OPENAI_ORGANIZATION]
* `--anthropic-api-key TEXT`: Anthropic API key, required for Anthropic models. [env var: ANTHROPIC_API_KEY]

### Model Configuration
* `--chat-model TEXT`: The model to use for chat completions. [env var: ELROY_CHAT_MODEL]
* `--embedding-model TEXT`: The model to use for text embeddings.
* `--embedding-model-size INTEGER`: The size of the embedding model.

### Context Management
* `--context-refresh-trigger-tokens INTEGER`: Number of tokens that triggers a context refresh and compression of messages.
* `--context-refresh-target-tokens INTEGER`: Target number of tokens after context refresh / compression.
* `--max-context-age-minutes FLOAT`: Maximum age in minutes to keep messages in context.
* `--context-refresh-interval-minutes FLOAT`: How often in minutes to refresh system message and compress context.
* `--min-convo-age-for-greeting-minutes FLOAT`: Minimum conversation age in minutes before offering a greeting on login.

### Memory Management
* `--l2-memory-relevance-distance-threshold FLOAT`: L2 distance threshold for memory relevance.
* `--l2-memory-consolidation-distance-threshold FLOAT`: L2 distance threshold for memory consolidation.
* `--initial-context-refresh-wait-seconds INTEGER`: Initial wait time in seconds before the first context refresh.

### UI Configuration
* `--show-internal-thought-monologue`: Show the assistant's internal thought monologue. [default: False]
* `--system-message-color TEXT`: Color for system messages. [default: #9ACD32]
* `--user-input-color TEXT`: Color for user input. [default: #FFE377]
* `--assistant-color TEXT`: Color for assistant output. [default: #77DFD8]
* `--warning-color TEXT`: Color for warning messages. [default: yellow]
* `--internal-thought-color TEXT`: Color for internal thought messages. [default: #708090]

### Logging
* `--log-file-path TEXT`: Where to write logs. [env var: ELROY_LOG_FILE_PATH]

### Shell Integration
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.


## License

Distributed under the GPL 3.0.1 License. See `LICENSE` for more information.
