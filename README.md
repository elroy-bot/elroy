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

Once installed locally you can:
```bash
# Start the chat interface
elroy chat

# Or just 'elroy' which defaults to chat mode
elroy

# Process a single message and exit
elroy message "Say hello world"

# Force use of a specific tool
elroy message "Create a reminder" --tool create_reminder

# Elroy also accepts stdin
echo "Say hello world" | elroy
```

## Memory and Reminder Tools
![Slash commands](images/slash_commands.gif)

Elroy's tools allow it to create and manager memories and reminders. In the background, redundant memories are consolidated.

As reminders or memories become relevant to the conversation, they are recalled into context. A `Relevant Context` panel makes all information being surfaced to the assistant available to the user.

All commands available to the assisstant are available to the user via `/` commands.

For a guide of what tools are available and what they do, see: [tools guide](docs/tools_guide.md).

For a full reference of tools and their schemas, see: [tools schema reference](docs/tools_schema.md)


### Configuration
Elroy is designed to be highly customizable, including CLI appearance and memory consolidation parameters.

For full configuration options, see [configuration documentation](docs/configuration.md).


### Supported Models

Elroy supports OpenAI, Anthropic, Google (Gemini), and any OpenAI-compatible API's.

Model aliases are available for quick selection:
- `--sonnet`: Anthropic's Sonnet model
- `--opus`: Anthropic's Opus model
- `--4o`: OpenAI's GPT-4o model
- `--4o-mini`: OpenAI's GPT-4o-mini model
- `--o1`: OpenAI's o1 model
- `--o1-mini`: OpenAI's o1-mini model


### Scripting Elroy

![Remember command](images/remember_command.gif)

You can script with elroy, using both the CLI package and the Python interface.

#### Python scripts
Elroy's API interface accepts the same parameters as the CLI. Scripting can be as simple as:


```python
ai = Elroy()

# some other task
ai.remember("This is how the task went")


# Elroy will automatically reference memory against incoming messages
ai.message("Here are memory augmented instructions")
```

To see a working example using, see [release_patch.py](scripts/release_patch.py)

#### Shell scripting

The chat interface accepts input from stdin, so you can pipe text to Elroy:
```bash
# Process a single question
echo "What is 2+2?" | elroy chat

# Create a memory from file content
cat meeting_notes.txt | elroy remember

# Use a specific tool with piped input
echo "Buy groceries" | elroy message --tool create_reminder
```

## Claude Code Integration

Elroy provides skills for [Claude Code](https://github.com/anthropics/claude-code) that expose memory management as slash commands:

- `/remember` - Create a long-term memory
- `/recall` - Search through memories
- `/list-memories` - List all memories
- `/remind` - Create a reminder
- `/list-reminders` - List active reminders
- `/ingest` - Ingest documents into memory
- `/introspect` - Ask questions about Elroy's implementation (for development)
- `/make-improvement` - Implement a feature or improvement and submit a PR (for development)

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
