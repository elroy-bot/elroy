# Claude Code Configuration for Elroy

## Build and Test Commands

**IMPORTANT**: This project uses [just](https://github.com/casey/just) as a command runner. Always use `just` commands instead of running build/test tools directly.

### Common Commands

- **Run tests**: `just test` (NOT `pytest` or `python -m pytest`)
- **Run specific test**: `just test <test_path>`
- **Build**: `just build` (NOT `python -m build` or similar)
- **Lint**: `just lint`
- **Format**: `just format`

### Why just?

The `just` command runner ensures:
- Correct environment setup
- Consistent command execution across different systems
- Proper dependency management
- Project-specific configurations are applied

### Finding Available Commands

Run `just --list` to see all available commands for this project.

## Development Workflow

When the user asks you to:
- "run the tests" → use `just test`
- "build the project" → use `just build`
- "check for lint errors" → use `just lint`
- "format the code" → use `just format`

Always prefer `just` commands over direct tool invocation.

## Project Roadmap

The project roadmap is maintained in `ROADMAP.md`. When working on features or discussing project direction:
- Reference the roadmap for current priorities
- Update the roadmap when completing items (move to "Completed" section)
- Add new items as they are identified or requested
- Keep items well-organized by category (Performance, Features, etc.)

## Elroy Agent Tools (Also Available as Claude Code Skills)

Elroy provides tools that are available both to the Elroy agent directly AND as Claude Code skills (via `/` commands).

### Memory Management Tools

These tools allow creating and managing long-term memories:

- **create_memory(name, text)** - Create a new long-term memory
  - Claude Code: `/remember "content"`
  - Example: `create_memory("Project preferences", "User prefers TypeScript")`

- **examine_memories(query)** - Search through memories
  - Claude Code: `/recall "query"`
  - Example: `examine_memories("authentication method")`

- **print_memories()** - List all active memories
  - Claude Code: `/list-memories`

- **create_reminder(name, text, trigger_datetime, reminder_context)** - Create a reminder
  - Claude Code: `/remind "content"`
  - Example: `create_reminder("Review PR", "Check the authentication PR", trigger_datetime="2025-01-26 14:00")`

- **print_active_reminders()** - List active reminders
  - Claude Code: `/list-reminders`

- **ingest_doc(path)** - Ingest documents into memory
  - Claude Code: `/ingest path`
  - Example: `ingest_doc("docs/architecture.md")`

### Self-Improvement Tools

These tools enable Elroy to understand and improve itself:

- **introspect(query)** - Ask questions about Elroy's implementation
  - Claude Code: `/introspect "query"`
  - Example: `introspect("How does memory consolidation work?")`
  - Returns: Detailed explanation with file paths and implementation details

- **make_improvement(description, create_branch, run_tests, submit_pr)** - Implement an improvement
  - Claude Code: `/make-improvement "description"`
  - Example: `make_improvement("Add date-aware search to examine_memories")`
  - Workflow: Plan → Implement → Test → Document → Submit PR
  - Returns: PR URL when submitted

- **review_roadmap()** - Review roadmap, issues, and recent commits
  - Example: `review_roadmap()`
  - Returns: Current project status and priorities

### Usage in Elroy Agent

When working as the Elroy agent (not in Claude Code), you can call these tools directly:

```python
# Understand implementation before making changes
result = introspect("How does the tool registry work?")

# Check project priorities
status = review_roadmap()

# Implement an improvement
pr_url = make_improvement(
    "Add better error messages for tool failures",
    create_branch=True,
    run_tests=True,
    submit_pr=True
)
```

### Usage in Claude Code

When working in Claude Code, use the slash command versions:

```bash
/introspect "How does memory consolidation work?"
/make-improvement "Add date-aware search"
/recall "project architecture decisions"
/remember "User prefers functional components"
```

### Development Workflow

The self-improvement tools create a complete feedback loop:

1. **Identify improvement** - Through usage patterns, user request, or review_roadmap()
2. **Understand current state** - Use introspect() to explore implementation
3. **Plan changes** - Review ROADMAP.md and issues with review_roadmap()
4. **Implement** - Use make_improvement() for structured implementation
5. **Submit for review** - PR created automatically with tests and documentation

This enables Elroy to actively participate in its own development.
