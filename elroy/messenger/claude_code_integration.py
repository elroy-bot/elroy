"""Integration layer for Claude Code skills accessible as Elroy tools.

This module provides implementations for self-improvement tools that bridge
Elroy's native tool system with Claude Code-style workflows.
"""

import subprocess
from pathlib import Path

from ..core.ctx import ElroyContext
from ..core.logging import get_logger

logger = get_logger(__name__)


def introspect_implementation(ctx: ElroyContext, query: str) -> str:
    """Explore Elroy's codebase to answer implementation questions.

    This is the implementation for the introspect() tool. It uses similar
    logic to the /introspect Claude Code skill.

    Args:
        ctx: The Elroy context
        query: Question about implementation

    Returns:
        Detailed explanation of the implementation
    """
    # Get the repository root (parent of elroy package)
    repo_root = Path(__file__).parent.parent.parent

    # Build a prompt for code exploration
    exploration_prompt = f"""Explore the Elroy codebase to answer this question: {query}

Repository structure:
- elroy/core/ - Core infrastructure (logging, latency, context, tracing)
- elroy/db/ - Database models and operations
- elroy/repository/ - Data access layer (memories, reminders, messages)
- elroy/tools/ - Agent tools and commands
- elroy/messenger/ - Message processing and agent loop
- elroy/cli/ - CLI interface
- elroy/config/ - Configuration management

Provide:
1. Summary - Brief answer to the question
2. Key Files - Relevant file paths with line numbers
3. How It Works - Explanation of the implementation
4. Related Code - Connected systems or patterns

Focus on being thorough and accurate. Include specific file paths and line numbers.
"""

    # For now, return a structured response that guides the agent
    # In a full implementation, this would use the Task/Explore agent
    return f"""To answer "{query}", I need to explore the codebase.

[Note: In production, this would use the Task/Explore agent to search the codebase.
For now, I can examine files directly using read/grep tools.]

Starting exploration at: {repo_root}

{exploration_prompt}

I'll now use file reading and search tools to investigate this question.
"""


def implement_improvement(
    ctx: ElroyContext,
    description: str,
    create_branch: bool = True,
    run_tests: bool = True,
    submit_pr: bool = True,
) -> str:
    """Implement an improvement following the make-improvement workflow.

    This is the implementation for the make_improvement() tool.

    Args:
        ctx: The Elroy context
        description: Description of improvement
        create_branch: Whether to create feature branch
        run_tests: Whether to run tests
        submit_pr: Whether to create PR

    Returns:
        Summary of actions taken
    """
    repo_root = Path(__file__).parent.parent.parent

    workflow_guide = f"""Implementing improvement: {description}

Workflow:
1. ✓ Understanding current implementation (use introspect() tool)
2. ✓ Review roadmap and issues (use review_roadmap() tool)
3. Plan the implementation
4. Get user approval
5. {"Create feature branch" if create_branch else "Work on current branch"}
6. Implement changes
7. {"Run tests" if run_tests else "Skip tests"}
8. Update documentation
9. {"Submit PR" if submit_pr else "Commit locally"}

Repository: {repo_root}

I'll now begin the workflow. First, let me understand the current implementation
by using the introspect() tool to investigate related code.
"""

    return workflow_guide


def review_project_status(ctx: ElroyContext) -> str:
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
