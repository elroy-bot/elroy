---
name: introspect
description: Ask questions about Elroy's implementation and codebase
disable-model-invocation: false
---

Ask questions about how Elroy is implemented. This skill helps you understand Elroy's codebase, architecture, and implementation details.

## Usage

When the user invokes this skill with `/introspect [QUERY]`, you should use the Task tool with the Explore agent to search through the Elroy codebase.

**IMPORTANT**: You are currently working in the Elroy repository at `/Users/tombedor/development/elroy`. Use the Task tool to explore the codebase.

### Example Task Tool Usage

```
Task tool with:
- subagent_type: "Explore"
- description: "Explore Elroy codebase"
- prompt: "<the user's query about implementation>"
- model: "sonnet" (for speed)
```

### What You Can Ask About

- **Architecture**: "How does memory consolidation work?"
- **Implementation**: "Where is the memory recall classifier implemented?"
- **Data models**: "What database tables exist?"
- **Tools**: "How are tools registered and executed?"
- **Configuration**: "What configuration options are available?"
- **Features**: "How do reminders work?"
- **Performance**: "What latency tracking exists?"

### Examples

User query: `/introspect "How does memory consolidation work?"`

You should:
1. Use the Task tool with Explore agent to search the codebase
2. Look for files related to consolidation (e.g., consolidation.py)
3. Examine relevant code
4. Provide a clear explanation of how it works

User query: `/introspect "Where is the latency tracker used?"`

You should:
1. Use Task/Explore to find latency.py and usage sites
2. Show where it's initialized and tracked
3. Explain the tracking mechanism

### Response Format

Provide:
1. **Summary**: Brief answer to the question
2. **Key Files**: List relevant file paths with line numbers
3. **How It Works**: Explanation of the implementation
4. **Related Code**: Any connected systems or patterns

### Repository Structure

The Elroy codebase is organized as:
- `elroy/core/` - Core infrastructure (logging, latency, context, tracing)
- `elroy/db/` - Database models and operations
- `elroy/repository/` - Data access layer (memories, reminders, messages)
- `elroy/tools/` - Agent tools and commands
- `elroy/messenger/` - Message processing and agent loop
- `elroy/cli/` - CLI interface
- `elroy/config/` - Configuration management
- `elroy/io/` - Input/output handling
- `claude-skills/` - Claude Code integration skills

### Notes

- Use the Explore agent for thorough searches across the codebase
- Include file paths with line numbers (e.g., `elroy/core/latency.py:45`)
- Explain not just "what" but "why" when possible
- Reference related systems and how they connect

This skill enables self-awareness - helping the agent understand its own implementation.
