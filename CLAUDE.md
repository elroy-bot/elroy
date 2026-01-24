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
