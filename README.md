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
- OpenAI key: Set the `OPENAI_API_KEY` environment variable

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
- Python 3.11 or higher
- OpenAI key: Set the `OPENAI_API_KEY` environment variable
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
- OpenAI key: Set the `OPENAI_API_KEY` environment variable
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

While chatting with Elroy, you can use the following commands. For the most part, these commands are available for Elroy to use autonomously:

### System Commands
- `/print_available_commands` - Show all available commands
- `/print_system_instruction` - View current system instructions
- `/refresh_system_instructions` - Refresh system instructions
- `/reset_system_context` - Reset conversation context
- `/print_context_messages` - View current conversation context

### Goal Management
- `/create_goal` - Create a new goal
- `/rename_goal` - Rename an existing goal
- `/print_goal` - View details of a specific goal
- `/add_goal_to_current_context` - Add a goal to current conversation
- `/drop_goal_from_current_context_only` - Remove goal from current conversation
- `/add_goal_status_update` - Update goal progress
- `/mark_goal_completed` - Mark a goal as complete
- `/delete_goal_permamently` - Delete a goal

### Memory Management
- `/print_memory` - View a specific memory
- `/create_memory` - Create a new memory

### User Preferences
- `/get_user_full_name` - Get your full name
- `/set_user_full_name` - Set your full name
- `/get_user_preferred_name` - Get your preferred name
- `/set_user_preferred_name` - Set your preferred name

### Conversation
- `/contemplate` - Ask Elroy to reflect on the conversation
- `/exit` - Exit the chat


## Customization

You can customize Elroy's appearance with these options:

- `--system-message-color TEXT` - Color for system messages
- `--user-input-color TEXT` - Color for user input
- `--assistant-color TEXT` - Color for assistant output
- `--warning-color TEXT` - Color for warning messages



## Options

* `--version`: Show version and exit.
* `--postgres-url TEXT`: Postgres URL to use for Elroy. If set, overrides use_docker_postgres. [env var: ELROY_POSTGRES_URL]
* `--openai-api-key TEXT`: OpenAI API key, required. [env var: OPENAI_API_KEY]
* `--context-window-token-limit INTEGER`: How many tokens to keep in context before compressing. Controls how much conversation history Elroy maintains before summarizing older content. [env var: ELROY_CONTEXT_WINDOW_TOKEN_LIMIT]
* `--log-file-path TEXT`: Where to write logs. [env var: ELROY_LOG_FILE_PATH; default: logs/elroy.log]
* `--use-docker-postgres / --no-use-docker-postgres`: If true and postgres_url is not set, will attempt to start a Docker container for Postgres. [env var: USE_DOCKER_POSTGRES; default: True]
* `--stop-docker-postgres-on-exit / --no-stop-docker-postgres-on-exit`: Whether or not to stop the Postgres container on exit. [env var: STOP_DOCKER_POSTGRES_ON_EXIT; default: False]
* `--show-internal-thought-monologue`: Show the assistant's internal thought monologue like memory consolidation and internal reflection. [default: False]
* `--system-message-color TEXT`: Color for system messages. [default: #9ACD32]
* `--user-input-color TEXT`: Color for user input. [default: #FFE377]
* `--assistant-color TEXT`: Color for assistant output. [default: #77DFD8]
* `--warning-color TEXT`: Color for warning messages. [default: yellow]
* `--internal-thought-color TEXT`: Color for internal thought messages. [default: #708090]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.


## License

Distributed under the GPL 3.0.1 License. See `LICENSE` for more information.
