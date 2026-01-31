"""Integration layer for Claude Code skills accessible as Elroy tools.

This module provides implementations for self-improvement tools that bridge
Elroy's native tool system with Claude Code-style workflows.
"""

import subprocess
from pathlib import Path

from ..core.ctx import ElroyContext
from ..core.logging import get_logger

logger = get_logger(__name__)


def introspect_implementation(ctx: ElroyContext, query: str) -> str:  # noqa: ARG001
    """Explore Elroy's codebase to answer implementation questions.

    This tool is designed to work when Elroy is running inside a Claude Code session.
    It returns a formatted request that Claude will see and act on by invoking
    the /introspect skill.

    Args:
        ctx: The Elroy context
        query: Question about implementation

    Returns:
        Formatted request for Claude to invoke /introspect skill
    """
    # Find where the elroy package is located
    elroy_path = Path(__file__).parent.parent.parent.resolve()

    # Check if it's a git repository (helpful context)
    is_git_repo = (elroy_path / ".git").exists()
    location_type = "git repository" if is_git_repo else "installed package"

    # Return a formatted request that Claude will recognize
    return f"""[INTROSPECT REQUEST]

Location: {elroy_path} ({location_type})
Query: {query}

Please invoke the /introspect skill to explore the Elroy codebase and answer this question.
The codebase is located at: {elroy_path}

If the working directory is not already {elroy_path}, you may need to reference that path when exploring."""


def implement_improvement(  # noqa: ARG001
    ctx: ElroyContext,
    description: str,
    create_branch: bool = True,
    run_tests: bool = True,
    submit_pr: bool = True,
) -> str:
    """Implement an improvement following the make-improvement workflow.

    This tool is designed to work when Elroy is running inside a Claude Code session.
    It returns a formatted request that Claude will see and act on by invoking
    the /make-improvement skill.

    Args:
        ctx: The Elroy context
        description: Description of improvement
        create_branch: Whether to create feature branch
        run_tests: Whether to run tests
        submit_pr: Whether to create PR

    Returns:
        Formatted request for Claude to invoke /make-improvement skill
    """
    repo_root = Path(__file__).parent.parent.parent.resolve()

    # Verify it's a git repository (required for making improvements)
    if not (repo_root / ".git").exists():
        return f"""[ERROR] Cannot make improvements to installed package

The Elroy code is located at: {repo_root}

This appears to be an installed package, not a git repository.
The make_improvement tool requires a git repository to:
- Create feature branches
- Commit changes
- Submit pull requests

Please run Elroy from a development checkout of the repository."""

    workflow_options = []
    if create_branch:
        workflow_options.append("create feature branch")
    if run_tests:
        workflow_options.append("run tests")
    if submit_pr:
        workflow_options.append("submit PR")

    options_str = ", ".join(workflow_options) if workflow_options else "commit locally only"

    return f"""[MAKE IMPROVEMENT REQUEST]

Location: {repo_root} (git repository)
Description: {description}
Options: {options_str}

Please invoke the /make-improvement skill with these parameters:
- create_branch={create_branch}
- run_tests={run_tests}
- submit_pr={submit_pr}

The /make-improvement skill will:
1. Use /introspect to understand current implementation
2. Use /review-roadmap to check priorities
3. Plan the implementation
4. Get your approval
5. Implement the changes
6. {'Create feature branch, ' if create_branch else ''}implement, {'run tests, ' if run_tests else ''}and {'submit PR' if submit_pr else 'commit locally'}"""


def review_project_status(ctx: ElroyContext) -> str:  # noqa: ARG001
    """Review roadmap, issues, and recent commits.

    Args:
        ctx: The Elroy context

    Returns:
        Summary of project status
    """
    repo_root = Path(__file__).parent.parent.parent
    roadmap_path = repo_root / "ROADMAP.md"

    sections = []

    # Read roadmap
    if roadmap_path.exists():
        with open(roadmap_path, "r") as f:
            sections.append("=== ROADMAP ===")
            sections.append(f.read())

    # Get recent commits
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            sections.append("\n=== RECENT COMMITS ===")
            sections.append(result.stdout)
    except Exception as e:
        logger.debug(f"Could not get git log: {e}")

    # Get open issues
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--limit", "10"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            sections.append("\n=== OPEN ISSUES ===")
            sections.append(result.stdout)
    except Exception as e:
        logger.debug(f"Could not get GitHub issues: {e}")

    return "\n".join(sections)
