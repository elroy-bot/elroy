<div align="center">
  <img src="images/logo_circle.png" alt="Elroy Logo" width="200"/>
</div>

# Elroy: An AI memory and reminder assistant

[![Discord](https://img.shields.io/discord/1200684659277832293?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://discord.gg/5PJUY4eMce)
[![GitHub](https://img.shields.io/github/stars/elroy-bot/elroy?style=social)](https://github.com/elroy-bot/elroy)
[![PyPI](https://img.shields.io/pypi/v/elroy)](https://pypi.org/project/elroy/)

Elroy is an AI assistant that runs in your terminal, with memory and powerful goal tracking. It remembers everything you tell it, can learn from your documents, and helps you stay organized.

![Goals Demo](images/goals_demo.gif)

## Features

- **Goal Tracking System**: Create, update, and track personal and professional goals
- **Memory**: Elroy automatically recalls relevant information from past conversations
- **Document Understanding**: Ingest your docs to give Elroy context about your projects
- **Simple Scripting**: Automate tasks with minimal configuration overhead
- **CLI Tool Interface**: Quickly review memories or jot notes for Elroy to remember
- **MCP Server**: Surface conversation memories to other tools via Model Context Protocol

The fastest way to get started is using the install script:

```bash
curl -LsSf https://raw.githubusercontent.com/elroy-bot/elroy/main/scripts/install.sh | sh
```

Or install manually with UV:

```bash
# Install UV first
curl -LsSf https://astral.sh/uv/install.sh | sh

# Then install Elroy
uv pip install elroy
```

For detailed installation instructions including Docker and source installation options, see the [Installation Guide](installation.md).

## Elroy from your terminal

![Remember Command](images/remember_command.gif)

Elroy runs in your terminal helps you with goals while maintaining memory of your interactions. As you chat with Elroy, it automatically:

1. **Creates memories** of important information
2. **Recalls relevant context** when needed
3. **Tracks goals** you set together
4. **Consolidates redundant information** to keep context clean

## Quickstart

Run the install script:
```
curl -LsSf https://raw.githubusercontent.com/elroy-bot/elroy/main/scripts/install.sh | sh
```

Ensure your env has `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or whatever model provider token you wish to use is set.

```bash
# Start the chat interface
elroy

# Run with a specific model
elroy --chat-model "gemini/gemini-2.0-flash"

# To see more detailed CLI options
elroy --help
```

## Slash Commands

![Slash Commands](images/slash_commands.gif)

Elroy's CLI supports slash commands for quick actions. Some examples (run `/help` to see the full list):

```bash
# Create a memory
/create_memory This is important information I want to save

# Create a goal
/create_goal Learn how to use Elroy effectively

# Process a single message and exit
elroy message "Say hello world"

# Force use of a specific tool
elroy message "Create a goal" --tool create_goal
```

## Scripting with Elroy

Elroy can be used in scripts and automated workflows:

```python
from elroy import Elroy

ai = Elroy()

# Create a memory
ai.remember("Important project context")

# Process a message with memory augmentation
response = ai.message("What should I do next on the project?")
print(response)
```

## Supported Models

Elroy works with:

- **OpenAI**: GPT-4o, GPT-4o-mini, o1, o1-mini
- **Anthropic**: Claude 3.5 Sonnet, Claude 3 Opus
- **Google**: Gemini
- Any OpenAI-compatible API

Under the hood, Elroy uses [LiteLLM](https://www.litellm.ai/) to interface with model providers.


## Community

Come say hello!

- [Discord](https://discord.gg/5PJUY4eMce)
- [GitHub](https://github.com/elroy-bot/elroy)

## License

Distributed under the Apache 2.0 license. See [LICENSE](https://github.com/elroy-bot/elroy/blob/main/LICENSE) for more information.
