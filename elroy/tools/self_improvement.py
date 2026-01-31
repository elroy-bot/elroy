"""Tools for Elroy to understand and improve itself."""

from ..core.constants import tool
from ..core.ctx import ElroyContext


@tool
def introspect(ctx: ElroyContext, query: str) -> str:
    """Ask questions about Elroy's implementation and codebase.

    Use this tool to understand how Elroy works internally. This helps when:
    - Planning improvements or new features
    - Understanding existing systems before modifying them
    - Debugging issues or unexpected behavior
    - Learning about architecture and design patterns

    The tool will explore the codebase and return a comprehensive explanation including:
    - Summary of how the queried feature works
    - Key file paths with line numbers
    - Related systems and connections
    - Implementation details and patterns

    Examples:
    - "How does memory consolidation work?"
    - "Where is the latency tracker used?"
    - "What database tables exist?"
    - "How are tools registered?"
    - "How does the memory recall classifier work?"

    Args:
        ctx: The Elroy context
        query: Question about Elroy's implementation

    Returns:
        Detailed explanation of the queried functionality
    """
    from ..messenger.claude_code_integration import introspect_implementation

    return introspect_implementation(ctx, query)


@tool
def make_improvement(
    ctx: ElroyContext,
    description: str,
    create_branch: bool = True,
    run_tests: bool = True,
    submit_pr: bool = True,
) -> str:
    """Implement a feature or improvement to Elroy and optionally submit a PR.

    Use this tool to make improvements to Elroy following a structured workflow:

    1. **Understanding & Planning**
       - Uses introspect() to understand current implementation
       - Reviews ROADMAP.md and GitHub issues
       - Creates implementation plan

    2. **Implementation**
       - Creates feature branch (if create_branch=True)
       - Implements the change
       - Follows existing code patterns

    3. **Testing**
       - Writes tests for new functionality
       - Runs `just test`, `just typecheck`, `just lint` (if run_tests=True)

    4. **Documentation**
       - Updates relevant documentation
       - Updates ROADMAP.md

    5. **Submission**
       - Commits changes with clear message
       - Pushes to remote
       - Creates pull request (if submit_pr=True)

    Examples:
    - "Add date-aware search to examine_memories"
    - "Improve error messages for tool failures"
    - "Add caching for embeddings responses"

    Args:
        ctx: The Elroy context
        description: Description of the improvement to make
        create_branch: Whether to create a feature branch (default: True)
        run_tests: Whether to run tests before submitting (default: True)
        submit_pr: Whether to create a pull request (default: True)

    Returns:
        Summary of what was done, including PR URL if submitted
    """
    from ..messenger.claude_code_integration import implement_improvement

    return implement_improvement(
        ctx,
        description,
        create_branch=create_branch,
        run_tests=run_tests,
        submit_pr=submit_pr,
    )


@tool
def review_roadmap(ctx: ElroyContext) -> str:
    """Review the current roadmap, open issues, and recent commits.

    Use this tool to understand:
    - What features are currently prioritized
    - What improvements are planned
    - What has been recently completed
    - What GitHub issues are open

    This helps identify what to work on next and ensures improvements
    align with project direction.

    Args:
        ctx: The Elroy context

    Returns:
        Summary of roadmap, issues, and recent work
    """
    from ..messenger.claude_code_integration import review_project_status

    return review_project_status(ctx)
