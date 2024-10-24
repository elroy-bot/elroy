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
pipx install --python python3.11 elroy
```

To run:
```
elroy
```

### 2. Docker Requirement

#### Prerequisites
- Docker: [Install Docker](https://docs.docker.com/get-docker/)
- Docker daemon must be running (Elroy uses it to create a PostgreSQL container)
- OpenAI key: Set the `OPENAI_API_KEY` environment variable

Note: You don't need to run Elroy in Docker - it just needs Docker running to manage its PostgreSQL database.

## License

Distributed under the GPL 3.0.1 License. See `LICENSE` for more information.
