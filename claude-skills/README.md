# Elroy Skills for Claude Code

This directory contains Claude Code skills that expose Elroy's memory management tools as slash commands.

## Overview

Elroy skills allow you to use Elroy's powerful memory management features directly from within Claude Code sessions. This creates a seamless integration between Claude Code and Elroy's long-term memory capabilities.

## Available Skills

| Skill | Description | Usage |
|-------|-------------|-------|
| `/remember` | Create a long-term memory | `/remember "User prefers TypeScript"` |
| `/recall` | Search through memories | `/recall "project preferences"` |
| `/list-memories` | List all active memories | `/list-memories` |
| `/remind` | Create a reminder | `/remind "Review PR tomorrow"` |
| `/list-reminders` | List active reminders | `/list-reminders` |
| `/ingest` | Ingest documents | `/ingest docs/` |

## Installation

### Prerequisites

1. **Elroy must be installed:**
   ```bash
   pip install elroy-ai
   ```

2. **Claude Code must be installed:**
   - Follow the installation instructions at [Claude Code repository](https://github.com/anthropics/claude-code)

### Install Skills

The easiest way to install skills is using the Elroy CLI:

```bash
elroy install-skills
```

This will:
- Copy all skill directories to `~/.claude/skills/` (or your configured skills directory)
- Make them available as slash commands in Claude Code
- **Restart your Claude Code session** to see the new skills

### Custom Installation Directory

If you use a custom skills directory:

```bash
elroy install-skills --skills-dir /path/to/your/skills
```

### Uninstall

To remove the Elroy skills:

```bash
elroy install-skills --uninstall
```

### Alternative: Manual Installation

You can also install manually using the installation script:

```bash
cd claude-skills
./install-skills.sh
```

For custom directories or other options, see `./install-skills.sh --help`

## Usage Examples

### Creating Memories

Store important information for long-term recall:

```bash
# In Claude Code session
/remember "User's project uses React with TypeScript and prefers functional components"
/remember "Authentication implemented using JWT tokens with 24-hour expiration"
```

### Searching Memories

Retrieve relevant information from past conversations:

```bash
/recall "What authentication method are we using?"
/recall "User's TypeScript preferences"
/recall "deployment configuration"
```

### Managing Reminders

Set time-based or context-based reminders:

```bash
/remind "Review the new feature branch tomorrow at 2pm"
/remind "Ask about test coverage when discussing testing strategy"
/list-reminders
```

### Ingesting Documentation

Make documentation available to Elroy for context:

```bash
/ingest README.md
/ingest docs/
/ingest specs/api-documentation.pdf
```

## How It Works

Each skill is a Claude Code skill (SKILL.md file with YAML frontmatter) that:

1. Appears as a slash command in Claude Code (e.g., `/remember`)
2. Instructs Claude to use Elroy's CLI commands via the Bash tool
3. Returns results back to the Claude Code session

The skills use Elroy's existing CLI commands:
- `elroy remember` - For creating memories
- `elroy message` - For executing tool commands like `/examine_memories`
- `elroy ingest` - For ingesting documents

After installation, restart your Claude Code session to see the new skills appear.

## Integration with Claude Code

When you use these skills in a Claude Code session, Claude can:

1. **Store Context**: Remember important decisions, preferences, and project details across sessions
2. **Retrieve Knowledge**: Search through past conversations and stored memories
3. **Set Reminders**: Create time-based or context-triggered reminders
4. **Ingest Docs**: Make project documentation available for recall

This creates a "memory layer" for Claude Code, allowing for more continuous and context-aware assistance.

## Configuration

The skills respect your existing Elroy configuration:

- **Database**: Uses your configured Elroy database (SQLite or PostgreSQL)
- **API Keys**: Uses your configured LLM API keys
- **Models**: Uses your default model configuration

Configuration is stored in:
- `~/.config/elroy/config.yml` (or `$XDG_CONFIG_HOME/elroy/config.yml`)
- Database at `~/.local/share/elroy/elroy.db` (default SQLite)

## Troubleshooting

### "elroy command not found"

Make sure Elroy is installed and in your PATH:

```bash
pip install elroy-ai
which elroy  # Should show the path to elroy executable
```

### Skills not appearing in Claude Code

1. **Restart Claude Code** - Skills are loaded at startup
2. Verify skills are installed: `ls ~/.claude/skills/*/SKILL.md`
3. Check the structure is correct:
   ```bash
   cat ~/.claude/skills/remember/SKILL.md
   ```
4. Type `/` in Claude Code to see all available skills

## Development

### Adding New Skills

To add a new Elroy skill:

1. Create a new directory in `claude-skills/` (e.g., `new-skill/`)
2. Create a `SKILL.md` file in that directory with YAML frontmatter:
   ```yaml
   ---
   name: new-skill
   description: What this skill does
   disable-model-invocation: false
   ---

   Instructions for Claude on how to use this skill...
   ```
3. Add the skill name to `SKILLS` array in:
   - `claude-skills/install-skills.sh`
   - `elroy/cli/main.py` (in the `install_skills` function)
4. Run `elroy install-skills` to install

### Skill Structure

Each skill directory contains:
- `SKILL.md` - Required. Contains YAML frontmatter and instructions for Claude
- Other files as needed (templates, examples, etc.)

Example SKILL.md:
```yaml
---
name: example
description: Example skill
disable-model-invocation: false
---

When the user invokes this skill, run:
```bash
elroy <command> "$ARGUMENTS"
```
```

## Related Documentation

- [Elroy Documentation](https://elroy.sh)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)
- [Elroy GitHub Repository](https://github.com/elroy-bot/elroy)

## License

These skills are part of the Elroy project and use the same license as Elroy.
