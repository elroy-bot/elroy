# Elroy

[![Discord](https://img.shields.io/discord/1200684659277832293?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://discord.gg/5PJUY4eMce)
[![Documentation](https://img.shields.io/badge/docs-elroy.bot-C8C7E8)](https://elroy.bot)
[![PyPI](https://img.shields.io/pypi/v/elroy)](https://pypi.org/project/elroy/)

Elroy is a scriptable, memory augmented AI personal assistant, accessible from the command line. It features:

- **Long-term Memory**: Automatic memory recall of past conversations
- **Goal Tracking**: Track and manage personal/professional goals
- **Simple scripting interface**: Script Elroy with minimal configuration overhead
- **CLI Tool interface**: Quickly review memories Elroy creates for you, or jot quick notes for Elroy to remember.
- **MCP server**: Surface conversation memories to other tools via MCP

![Goals Demo](images/goals_demo.gif)


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
elroy message "Create a goal" --tool create_goal

# Elroy also accepts stdin
echo "Say hello world" | elroy
```

## Memory and Goal Tools
![Slash commands](images/slash_commands.gif)

Elroy's tools allow it to create and manager memories and goals. In the background, redundant memories are consolidated.

As goals or memories become relevant to the conversation, they are recalled into context. A `Relevant Context` panel makes all information being surfaced to the assistant available to the user.

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
echo "Buy groceries" | elroy message --tool create_goal
```

## MCP Server

To configure an MCP client to use Elroy:

1. Ensure `uv` is installed
1. Use `elroy mcp print-config` to get the server's json configuration
1. Paste the value in the client's MCP server config.

MCP support is experimental, please file issues if you encounter problems!

## Roadmap

For information about upcoming features, planned changes, and project direction, see the [roadmap](docs/roadmap.md).

## License

Distributed under the Apache 2.0 license. See LICENSE for more information.

## Contact

Bug reports and feature requests are welcome via [GitHub](https://github.com/elroy-bot/elroy/issues)

Get in touch on [Discord](https://discord.gg/5PJUY4eMce) or via [email](hello@elroy.bot)
