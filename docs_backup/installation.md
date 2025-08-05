# Installation Guide

## Prerequisites

- Relevant API keys (for simplest setup, set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)
- Database, either:
    - SQLite (sqlite-vec will be installed)
    - PostgreSQL with pgvector extension

By default, Elroy will use SQLite. To add a custom DB, you can provide your database url either via the `ELROY_DATABASE_URL`, the `database_url` config value, or via the `--database-url` startup flag.

## Option 1: Using Install Script (Recommended)

```bash
curl -LsSf https://raw.githubusercontent.com/elroy-bot/elroy/main/scripts/install.sh | sh
```

This will:
- Install uv if not already present
- Install Python 3.12 if needed
- Install Elroy in an isolated environment
- Add Elroy to your PATH

This install script is based on [Aider's installation script](https://aider.chat/2025/01/15/uv.html)

## Option 2: Using UV Manually

### Prerequisites
- Python 3.10 or higher
- Database (SQLite or PostgreSQL with pgvector extension)
- Relevant API keys (for simplest setup, set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)

1. Install UV:
```bash
# On Unix-like systems (macOS, Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. Install and run Elroy:
```bash
# Install Elroy
uv pip install elroy

# Run Elroy
elroy

# Or install in an isolated environment
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows
uv pip install elroy
elroy
```

## Option 3: Using Docker

### Prerequisites
- Docker and Docker Compose

This option automatically sets up everything you need, including the required PostgreSQL database with pgvector extension.

1. Download the docker-compose.yml:
```bash
curl -O https://raw.githubusercontent.com/elroy-bot/elroy/main/docker-compose.yml
```

2. Run Elroy:
```bash
# to ensure you have the most up to date image
docker compose build --no-cache
docker compose run --rm elroy

# Add parameters as needed, e.g. here to use Anthropic's Sonnet model
docker compose run --rm elroy --sonnet

# Pass through all environment variables from host
docker compose run --rm -e elroy

# Or pass specific environment variable patterns
docker compose run --rm -e "ELROY_*" -e "OPENAI_*" -e "ANTHROPIC_*" elroy
```

The Docker image is publicly available at `ghcr.io/elroy-bot/elroy`.

## Option 4: Installing from Source

### Prerequisites
- Python 3.10 or higher
- uv package manager (install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Relevant API keys (for simplest setup, set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)
- PostgreSQL database with pgvector extension

```bash
# Clone the repository
git clone --single-branch --branch stable https://github.com/elroy-bot/elroy.git
cd elroy

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Unix/MacOS
# or
.venv\Scripts\activate  # On Windows

# Install dependencies and the package
uv pip install -e .

# Run Elroy
elroy
```
