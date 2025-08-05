---
sidebar_position: 1
---

# Welcome to Elroy

<div align="center">
  <img src="/images/logo_circle.png" alt="Elroy Logo" width="200"/>
</div>

**Elroy is an AI assistant that runs in your terminal, with memory and powerful goal tracking.** It remembers everything you tell it, can learn from your documents, and helps you stay organized.

![Goals Demo](/images/goals_demo.gif)

## Features

- **Goal Tracking System**: Create, update, and track personal and professional goals
- **Memory**: Elroy automatically recalls relevant information from past conversations
- **Document Understanding**: Ingest your docs to give Elroy context about your projects
- **Simple Scripting**: Automate tasks with minimal configuration overhead
- **CLI Tool Interface**: Quickly review memories or jot notes for Elroy to remember
- **MCP Server**: Surface conversation memories to other tools via Model Context Protocol

## Quick Start

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

For detailed installation instructions including Docker and source installation options, see the [Installation Guide](installation).

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
