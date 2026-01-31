---
name: make-improvement
description: Implement a feature or improvement to Elroy and submit a PR
disable-model-invocation: false
---

Implement an improvement to Elroy following a structured workflow. This skill guides you through understanding, implementing, testing, and submitting changes as a pull request.

## Usage

When the user invokes this skill with `/make-improvement [DESCRIPTION]`, follow this comprehensive workflow to implement and submit the change.

**IMPORTANT**: You are working in the Elroy repository at `/Users/tombedor/development/elroy`. All commands should be run from this directory.

## Workflow

### Phase 1: Understanding & Planning

#### 1.1 Understand Current Implementation
Use `/introspect` to understand relevant code:
```
/introspect "How does [relevant system] work?"
```

#### 1.2 Review Context
- Check `ROADMAP.md` for alignment with project direction
- Check open issues: `gh issue list`
- Review recent commits: `git log --oneline -10`

#### 1.3 Plan the Implementation
Create a clear implementation plan:
- What files will change?
- What new files are needed?
- What's the approach?
- Are there edge cases to consider?
- What tests are needed?

**Ask the user for approval of the plan before proceeding.**

### Phase 2: Implementation

#### 2.1 Create Feature Branch
```bash
git checkout -b feature/[descriptive-name]
```

#### 2.2 Implement the Change
- Write clean, focused code
- Follow existing code style and patterns
- Add docstrings for new functions/classes
- Consider error handling and edge cases

#### 2.3 Update Configuration (if needed)
If adding new config options:
- Add to relevant config dataclass in `elroy/core/configs.py`
- Document in `docs/configuration.md`

### Phase 3: Testing

#### 3.1 Write Tests
Add tests in `tests/` directory:
- Unit tests for new functionality
- Integration tests if needed
- Follow existing test patterns

#### 3.2 Run Tests
```bash
just test
```

If tests fail, fix issues and re-run.

#### 3.3 Run Type Checking
```bash
just typecheck
```

#### 3.4 Run Linting
```bash
just lint
```

Fix any issues found.

### Phase 4: Documentation

#### 4.1 Update Documentation
As appropriate:
- Update `README.md` if user-facing feature
- Update relevant docs in `docs/`
- Add examples if helpful
- Update `ROADMAP.md` (move item to Completed section)

#### 4.2 Write Clear Commit Message
Follow the repository's commit message style (check recent commits):
- Brief summary (50 chars or less)
- Blank line
- Detailed explanation of what and why
- Reference any related issues

### Phase 5: Submit PR

#### 5.1 Commit Changes
```bash
git add [files]
git commit -m "$(cat <<'EOF'
[Imperative summary of change]

[Detailed explanation of what was changed and why]

[Any relevant notes, breaking changes, or migration steps]

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

#### 5.2 Push Branch
```bash
git push -u origin feature/[descriptive-name]
```

#### 5.3 Create Pull Request
```bash
gh pr create --title "[PR Title]" --body "$(cat <<'EOF'
## Summary
[Brief description of what this PR does]

## Changes
- [List of key changes]
- [Another change]

## Testing
- [How this was tested]
- [What tests were added]

## Documentation
- [Documentation updates made]

## Related Issues
Closes #[issue-number] (if applicable)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

#### 5.4 Return PR URL
Show the user the PR URL so they can review and merge.

## Best Practices

### Code Quality
- Follow existing patterns in the codebase
- Keep changes focused and minimal
- Don't refactor unrelated code
- Write self-documenting code with clear names

### Testing
- Test both success and failure cases
- Test edge cases
- Ensure tests are reliable (not flaky)
- Use existing test fixtures and utilities

### Documentation
- Document new configuration options
- Update user-facing docs for new features
- Include usage examples
- Keep documentation concise and clear

### Git Hygiene
- One feature per PR
- Atomic commits (each commit should work)
- Clear commit messages
- Don't commit debug code or unnecessary changes

## Example Workflow

User: `/make-improvement "Add date-aware search to examine_memories"`

You should:

1. **Understand**: `/introspect "How does examine_memories work?"`
2. **Plan**:
   - Modify `elroy/tools/memories/tools.py` to add date parsing
   - Use existing `dateparser` library (already in dependencies for reminders)
   - Add date range filter to vector search
   - Fall back to text search if no dates detected
3. **Get approval**: "Here's my plan: [explain]. Does this look good?"
4. **Implement**:
   - Create branch: `feature/date-aware-memory-search`
   - Modify `examine_memories()` function
   - Add helper function `extract_date_range()`
5. **Test**:
   - Add tests in `tests/tools/test_memory_tools.py`
   - Test various date formats
   - Test fallback to text search
   - Run `just test`
6. **Document**:
   - Update tool docstring
   - Add example to `docs/tools_guide.md`
7. **Submit**:
   - Commit with clear message
   - Push to origin
   - Create PR with `gh pr create`
   - Return PR URL

## Troubleshooting

### Tests Failing
- Read the test output carefully
- Fix the issue
- Re-run tests
- Don't skip failing tests

### Type Errors
- Run `just typecheck` to see issues
- Fix type annotations
- Use `Optional[]` for nullable values
- Add type hints to new functions

### Lint Errors
- Run `just lint` to see issues
- Run `just format` to auto-fix formatting
- Fix remaining issues manually

### Merge Conflicts
- Pull latest main: `git pull origin main`
- Resolve conflicts
- Re-run tests
- Push updated branch

## Configuration Files

- **Tests**: Use `just test` (NOT direct pytest)
- **Linting**: Use `just lint`
- **Formatting**: Use `just format`
- **Type checking**: Use `just typecheck`

See `CLAUDE.md` in the repository for more details on the build system.

## Notes

- Always use `just` commands, not direct tool invocation
- Check `justfile` with `just --list` for available commands
- Follow the repository's conventions (check existing code)
- Ask for user approval before major changes
- Keep the user informed of progress
- If stuck, use `/introspect` to understand more

This skill completes the self-improvement loop - enabling Elroy to implement improvements to itself.
