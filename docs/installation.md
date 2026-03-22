# Installation Guide

## Prerequisites

- Python 3.12
- Relevant API keys (for simplest setup, set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)
- SQLite (included with Python; sqlite-vec will be installed automatically)

By default, Elroy uses SQLite. To use a custom database path, set `ELROY_DATABASE_URL` or the `database_url` config value.

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
- Python 3.12
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

1. Download the docker-compose.yml:
```bash
curl -O https://raw.githubusercontent.com/elroy-bot/elroy/main/docker-compose.yml
```

2. Run Elroy:
```bash
# to ensure you have the most up to date image
docker compose build --no-cache
docker compose run --rm elroy

# Pass through all environment variables from host
docker compose run --rm -e OPENAI_API_KEY -e ANTHROPIC_API_KEY elroy

# Or pass specific environment variable patterns
docker compose run --rm -e "ELROY_*" -e "OPENAI_*" -e "ANTHROPIC_*" elroy
```

The Docker image is publicly available at `ghcr.io/elroy-bot/elroy`.

## Option 4: Installing from Source

### Prerequisites
- Python 3.12
- uv package manager (install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Relevant API keys (for simplest setup, set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)

```bash
# Clone the repository
git clone --single-branch --branch stable https://github.com/elroy-bot/elroy.git
cd elroy

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows

# Install dependencies and the package
uv pip install -e .

# Run Elroy
elroy
```
