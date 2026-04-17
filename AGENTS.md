# Agent Instructions for Elroy

## Build and Test Commands

**IMPORTANT**: This project uses [just](https://github.com/casey/just) as a command runner. Always use `just` commands instead of running build/test tools directly.

### Common Commands

- **Run tests**: `just test` (NOT `pytest` or `python -m pytest`)
- **Run specific test**: `just test <test_path>`
- **Build**: `just build` (NOT `python -m build` or similar)
- **Lint**: `just lint`
- **Format**: `just format`

### Finding Available Commands

Run `just --list` to see all available commands for this project.

## Code Review Standard

Use `CODE_REVIEW.md` as the source of truth for code review expectations in this repository.

During review:
- Apply the role, dependency, and validation rules defined in `CODE_REVIEW.md`
- Do not duplicate or invent competing review standards in review comments
- Treat `just lint` and `just typecheck` as required validation before code is ready for review

## Project Roadmap

Reference `ROADMAP.md` for current priorities, and update it when completing roadmap items or adding new ones.
