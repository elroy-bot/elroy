# Elroy

Elroy is an CLI AI personal assistant with long term memory and goal tracking capabilities.

## Installation

There are two ways to install and run Elroy:

### 1. Using pipx (Recommended)

#### Prerequisites
- Python 3.11 or higher
- pipx: Install with `python3.11 -m pip install --user pipx`
- OpenAI key: Set the `OPENAI_API_KEY` environment variable

#### Installation
```
pip install elroy
```

To run:
```
elroy
```

### System Requirements

Elroy requires Python > 3.11

### Database Requirement

Elroy needs a PostgreSQL database. By default, it will use Docker to automatically manage a PostgreSQL instance for you. You have two options:

1. Let Elroy manage PostgreSQL (Default):
   - Requires Docker to be installed and running
   - Elroy will automatically create and manage a PostgreSQL container

2. Use your own PostgreSQL (Advanced):
   - Set ELROY_POSTGRES_URL to your database connection string
   - Docker is not required in this case

In either case, you'll need:
- OpenAI key: Set the `OPENAI_API_KEY` environment variable



## Options

* `--version`: Show version and exit.
* `--postgres-url TEXT`: Postgres URL to use for Elroy. If set, ovverrides use_docker_postgres.  [env var: ELROY_POSTGRES_URL]
* `--openai-api-key TEXT`: OpenAI API key, required.  [env var: OPENAI_API_KEY]
* `--context-window-token-limit INTEGER`: How many tokens to keep in context before compressing.  [env var: ELROY_CONTEXT_WINDOW_TOKEN_LIMIT]
* `--log-file-path TEXT`: Where to write logs.  [env var: ELROY_LOG_FILE_PATH; default: /Users/tombedor/development/elroy/logs/elroy.log]
* `--use-docker-postgres / --no-use-docker-postgres`: If true and postgres_url is not set, will attempt to start a Docker container for Postgres.  [env var: USE_DOCKER_POSTGRES; default: use-docker-postgres]
* `--stop-docker-postgres-on-exit / --no-stop-docker-postgres-on-exit`: Whether or not to stop the Postgres container on exit.  [env var: STOP_DOCKER_POSTGRES_ON_EXIT; default: no-stop-docker-postgres-on-exit]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.


## License

Distributed under the GPL 3.0.1 License. See `LICENSE` for more information.
