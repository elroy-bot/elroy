<div align="center">
  <img src="images/logo_circle.png" alt="Elroy Logo" width="200"/>
</div>

# Overview

Elroy is an AI assistant that runs in your terminal, with memory and agenda tracking. It remembers what you tell it, can learn from your documents, and helps you stay organized.

[![Discord](https://img.shields.io/discord/1200684659277832293?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://discord.gg/5PJUY4eMce)
[![GitHub](https://img.shields.io/github/stars/elroy-bot/elroy?style=social)](https://github.com/elroy-bot/elroy)
[![PyPI](https://img.shields.io/pypi/v/elroy)](https://pypi.org/project/elroy/)

![Due-item demo](images/reminders_demo.gif)

## Features

- **Agenda and Due Items**: Create file-backed agenda items, including items that trigger by time or context
- **Memory**: Elroy automatically recalls relevant information from past conversations
- **Document Understanding**: Ingest your docs to give Elroy context about your projects
- **Simple Scripting**: Automate tasks with minimal configuration overhead
- **CLI Tool Interface**: Quickly review memories or jot notes for Elroy to remember

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

Elroy runs in your terminal and helps you manage agenda items and due work while maintaining memory of your interactions. As you chat with Elroy, it automatically:

1. **Creates memories** of important information
2. **Recalls relevant context** when needed
3. **Tracks agenda items and due items** you set together
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
ELROY_CHAT_MODEL=gemini/gemini-2.0-flash elroy
```

## Slash Commands

![Slash Commands](images/slash_commands.gif)

Elroy's TUI supports slash commands for quick actions. Some examples (run `/help` to see the full list):

```bash
# Create a memory
/create_memory This is important information I want to save

# Create a due item
/create_due_item Learn how to use Elroy effectively

# Search memories
/search_memories project notes

# Show configuration
/print_config
```

## Supported Models

Elroy works with:

- **OpenAI**: GPT-5, GPT-5-mini, o1
- **Anthropic**: Claude 4.5 Sonnet, Claude 4.5 Opus, Claude 3.5 Haiku
- **Google**: Gemini 2.0 Flash
- Any OpenAI-compatible API

Under the hood, Elroy uses [LiteLLM](https://www.litellm.ai/) to interface with model providers.


## Community

Come say hello!

- [Discord](https://discord.gg/5PJUY4eMce)
- [GitHub](https://github.com/elroy-bot/elroy)

## License

Distributed under the Apache 2.0 license. See [LICENSE](https://github.com/elroy-bot/elroy/blob/main/LICENSE) for more information.
