# CLI

Elroy provides a powerful command-line interface that makes it easy to interact with the AI assistant directly from your terminal.

## Basic Usage

```bash
# Start the chat interface
elroy chat

# Or just 'elroy' which defaults to chat mode
elroy

# Process a single message and exit
elroy message "Say hello world"

# Create a memory
elroy remember "This is important information I want to save"
```

## Slash Commands

Elroy supports powerful slash commands for quick actions:

<div align="center">
  <img src="../images/slash_commands.gif" alt="Slash Commands demonstration" style="max-width: 100%; margin: 20px 0;">
</div>

```bash
# Create a memory
/create_memory This is important information I want to save

# Create a reminder
/create_reminder Learn how to use Elroy effectively

```

For a full list of available tools and slash commands, see the [Tools Guide](tools_guide.md).

## Command Reference

| Command | Description |
|---------|-------------|
| `elroy chat` | Opens an interactive chat session (default command) |
| `elroy message TEXT` | Process a single message and exit. Use `--plain` for plaintext output instead of rich text |
| `elroy remember [TEXT]` | Create a new memory from text or interactively |
| `elroy ingest PATH` | Ingests document(s) at the given path into memory. Can process single files or directories |
| `elroy list-models` | Lists supported chat models and exits |
| `elroy list-tools` | Lists all available tools |
| `elroy print-config` | Shows current configuration and exits |
| `elroy version` | Show version and exit |
| `elroy print-tool-schemas` | Prints the schema for a tool and exits |
| `elroy set-persona TEXT` | Set a custom persona for the assistant |
| `elroy reset-persona` | Removes any custom persona, reverting to the default |
| `elroy show-persona` | Print the system persona and exit |

## Document Ingestion

Elroy supports ingesting documents to make their content available for memory and retrieval:

```bash
# Ingest a single file
elroy ingest document.md

# Ingest all files in a directory
elroy ingest ./documents/

# Ingest recursively with pattern matching
elroy ingest ./documents/ --recursive --include "*.md,*.txt" --exclude "*.log"
```

### Ingest Command Options

| Option | Description |
|--------|-------------|
| `--force-refresh, -f` | If true, any existing ingested documents will be discarded and re-ingested |
| `--recursive, -r` | If path is a directory, recursively ingest all documents within it |
| `--include, -i` | Glob pattern for files to include (e.g., '*.txt,*.md'). Multiple patterns can be comma-separated |
| `--exclude, -e` | Glob pattern for files to exclude (e.g., '*.log'). Can also be used to exclude directories |

## Shell Integration

Elroy can be used in scripts and automated workflows:

```bash
# Process a single question
echo "What is 2+2?" | elroy chat

# Create a memory from file content
cat meeting_notes.txt | elroy remember

# Use a specific tool with piped input
echo "Buy groceries" | elroy message --tool create_reminder
```
