# Elroy

[![Discord](https://img.shields.io/discord/1200684659277832293?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://discord.gg/5PJUY4eMce)
[![Documentation](https://img.shields.io/badge/docs-elroy.bot-C8C7E8)](https://elroy.bot)
[![PyPI](https://img.shields.io/pypi/v/elroy)](https://pypi.org/project/elroy/)

Elroy is a scriptable, memory augmented AI personal assistant, accessible from the command line. It features:

- **Long-term Memory**: Automatic memory recall of past conversations
- **Reminders** Track context based and timing based reminders
- **Simple scripting interface**: Script Elroy with minimal configuration overhead
- **CLI Tool interface**: Quickly review memories Elroy creates for you, or jot quick notes for Elroy to remember.

![Reminder demo](./docs/images/reminders_demo.gif)


## Quickstart

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

For detailed installation instructions including Docker and source installation options, see the [Installation Guide](docs/installation.md).

## Basic Usage

Once installed, run `elroy` to open the interactive chat interface:

```bash
elroy
```

Elroy opens a terminal UI where you can chat, create memories, and manage reminders. Use `/help` inside the chat to see available slash commands.

## Memory and Reminder Tools
![Slash commands](images/slash_commands.gif)

Elroy's tools allow it to create and manage memories and reminders. In the background, redundant memories are consolidated.

As reminders or memories become relevant to the conversation, they are recalled into context. A `Relevant Context` panel makes all information being surfaced to the assistant available to the user.

All commands available to the assistant are also available to the user via `/` slash commands in the chat interface.

For a guide of what tools are available and what they do, see: [tools guide](docs/tools_guide.md).

For a full reference of tools and their schemas, see: [tools schema reference](docs/tools_schema.md)


### Configuration
Elroy is designed to be highly customizable, including appearance and memory consolidation parameters.

Configuration can be provided via environment variables (e.g. `ELROY_CHAT_MODEL=gpt-5`) or a config file at `~/.elroy/elroy.conf.yaml`.

For full configuration options, see [configuration documentation](docs/configuration/index.md).


### Supported Models

Elroy supports OpenAI, Anthropic, Google (Gemini), and any OpenAI-compatible API.

The model is selected automatically based on which API key is set, or can be configured explicitly:

```bash
# Use an Anthropic model
ELROY_CHAT_MODEL=claude-sonnet-4-5-20250929 elroy

# Use a specific OpenAI model
ELROY_CHAT_MODEL=gpt-5 elroy

# Use Gemini
ELROY_CHAT_MODEL=gemini/gemini-2.0-flash elroy
```

Common model aliases can be used as the `chat_model` config value:
- `sonnet`: Anthropic's Claude 4.5 Sonnet
- `opus`: Anthropic's Claude 4.5 Opus
- `haiku`: Anthropic's Claude 3.5 Haiku
- `o1`: OpenAI's o1 model

## Claude Code Integration

Elroy provides skills for [Claude Code](https://github.com/anthropics/claude-code) that expose memory management as slash commands:

- `/remember` - Create a long-term memory
- `/recall` - Search through memories
- `/list-memories` - List all memories
- `/remind` - Create a reminder
- `/list-reminders` - List active reminders
- `/ingest` - Ingest documents into memory

### Installation

Install the Claude Code skills using the Elroy CLI:

```bash
elroy install-skills
```

Or use the just command from the repository:

```bash
just install-claude-skills
```

This installs skills to `~/.claude/skills/` making them available in all Claude Code sessions.

**Important**: Restart your Claude Code session after installation to load the new skills.

To uninstall:

```bash
elroy install-skills --uninstall
```

For detailed usage and examples, see [claude-skills/README.md](claude-skills/README.md).

## Branches

`main` comes with backwards compatibility and automatic database migrations.

`stable` is sync'd with the latest release branch.

`experimental` is a test branch with upcoming changes. These may contain breaking changes and/or changes that do not come with automatic database migrations.

## License

Distributed under the Apache 2.0 license. See LICENSE for more information.

## Contact

Bug reports and feature requests are welcome via [GitHub](https://github.com/elroy-bot/elroy/issues)

Get in touch on [Discord](https://discord.gg/5PJUY4eMce) or via [email](hello@elroy.bot)
