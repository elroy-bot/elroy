"""Self-diagnosis system for intelligent error analysis.

This module provides LLM-powered error diagnosis to help users understand
and fix errors without requiring bug reports. When errors occur, the system:
1. Gathers comprehensive diagnostic context
2. Analyzes the error using LLM
3. Provides user-friendly explanations
4. Suggests specific fixes the user can implement
"""

from enum import Enum
from typing import List

from pydantic import BaseModel

from ..core.ctx import ElroyContext
from ..core.error_context import DiagnosticContext, gather_diagnostic_context
from ..core.logging import get_logger
from ..io.cli import CliIO

logger = get_logger()


class FixType(str, Enum):
    """Type of fix suggested."""

    CONFIG = "config"  # Configuration file change  # noqa: F841
    INSTALL = "install"  # Install/update dependency  # noqa: F841
    MANUAL = "manual"  # Manual action needed  # noqa: F841
    ENVIRONMENT = "environment"  # Environment variable change  # noqa: F841


class SuggestedFix(BaseModel):
    """A specific fix suggestion."""

    description: str  # Brief description of the fix
    fix_type: FixType  # Type of fix
    instructions: str  # Step-by-step instructions


class DiagnosisResult(BaseModel):
    """Structured diagnosis from LLM."""

    error_summary: str  # Brief one-sentence summary
    root_cause: str  # Technical root cause explanation
    user_explanation: str  # User-friendly explanation
    suggested_fixes: List[SuggestedFix]  # Ordered list of fixes (best first)
    confidence: float  # Confidence score (0.0 to 1.0)


class DiagnosisEngine:
    """Engine for analyzing errors and providing intelligent diagnosis."""

    def __init__(self, ctx: ElroyContext):
        """Initialize the diagnosis engine.

        Args:
            ctx: ElroyContext for accessing LLM and configuration
        """
        self.ctx = ctx

    def diagnose(self, error: Exception) -> DiagnosisResult:
        """Analyze an error and provide structured diagnosis.

        Args:
            error: The exception to diagnose

        Returns:
            DiagnosisResult with analysis and suggested fixes

        Raises:
            Exception: If diagnosis itself fails
        """
        # Gather comprehensive context
        max_log_lines = getattr(self.ctx, "diagnosis_max_log_lines", 50)
        diagnostic_context = gather_diagnostic_context(self.ctx, error, max_log_lines)

        # Build prompt for LLM analysis
        prompt = self._build_diagnosis_prompt(diagnostic_context)
        system_message = self._build_system_message()

        # Query LLM for structured diagnosis
        diagnosis = self.ctx.fast_llm.query_llm_with_response_format(
            prompt=prompt,
            system=system_message,
            response_format=DiagnosisResult,
        )

        logger.debug(f"Error diagnosis completed: {diagnosis.error_summary} (confidence: {diagnosis.confidence})")

        return diagnosis

    def _build_system_message(self) -> str:
        """Build the system message for diagnosis LLM."""
        return """You are an expert error diagnosis system for Elroy, an AI assistant application.
Your job is to analyze errors and help users fix them quickly and effectively.

Key principles:
- Provide clear, actionable fixes
- Explain technical issues in user-friendly language
- Order fixes from most likely to least likely to work
- Be specific with file paths, commands, and configuration
- Consider common issues: API keys, model names, database connections, dependencies
- Use appropriate fix types: CONFIG, INSTALL, ENVIRONMENT, MANUAL
- Provide step-by-step instructions
- Be confident but honest about uncertainty (use confidence score)"""

    def _build_diagnosis_prompt(self, context: DiagnosticContext) -> str:
        """Build the prompt for LLM diagnosis.

        Args:
            context: Diagnostic context gathered from the error

        Returns:
            Formatted prompt for the LLM
        """
        return f"""Analyze this error from Elroy and provide a diagnosis with fixes.

ERROR INFORMATION:
Error Type: {context.error_type}
Error Message: {context.error_message}

TRACEBACK:
{context.traceback}

RECENT LOGS:
{context.recent_logs}

SYSTEM INFORMATION:
{self._format_dict(context.system_info)}

CONFIGURATION:
{self._format_dict(context.config_summary)}

ANALYSIS REQUIRED:
1. error_summary: One sentence describing what happened
2. root_cause: Technical explanation of why this error occurred
3. user_explanation: User-friendly explanation of the problem
4. suggested_fixes: List of specific fixes (ordered best to worst)
   - Each fix should have: description, fix_type, and step-by-step instructions
   - Be specific about file paths, commands, and settings
   - Include exact configuration values if applicable
5. confidence: Your confidence in this diagnosis (0.0-1.0)

Common error patterns to check:
- Missing/invalid API keys → ENVIRONMENT fix
- Invalid model names → CONFIG fix
- Database connection issues → CONFIG or INSTALL fix
- Missing dependencies → INSTALL fix
- File/directory not found → CONFIG or MANUAL fix
- Tool loading errors → CONFIG fix

Provide actionable, specific fixes that the user can implement immediately."""

    def _format_dict(self, d: dict) -> str:
        """Format a dictionary for display in the prompt."""
        return "\n".join(f"  {k}: {v}" for k, v in d.items())


def handle_error_with_diagnosis(io: CliIO, ctx: ElroyContext, error: Exception) -> None:
    """Main entry point for error diagnosis.

    This function replaces the bug report flow. When an error occurs:
    1. Gather diagnostic context
    2. Analyze with LLM
    3. Display diagnosis to user
    4. Show suggested fixes
    5. Suggest restart after fixes

    Args:
        io: CliIO for user interaction
        ctx: ElroyContext for accessing LLM
        error: The exception that occurred
    """
    try:
        # Create diagnosis engine and analyze error
        engine = DiagnosisEngine(ctx)
        diagnosis = engine.diagnose(error)

        # Display diagnosis to user
        _display_diagnosis(io, ctx, diagnosis)

    except Exception as diagnosis_error:
        # If diagnosis itself fails, show simple error and exit gracefully
        logger.error(f"Self-diagnosis failed: {diagnosis_error}", exc_info=True)
        io.warning("Error diagnosis system encountered an issue.")
        io.warning(f"Original error: {error.__class__.__name__}: {str(error)}")
        io.info("Please check the logs at ~/.elroy/logs/elroy.log for more details.")


def _display_diagnosis(io: CliIO, ctx: ElroyContext, diagnosis: DiagnosisResult) -> None:
    """Display the diagnosis result to the user in a formatted way.

    Args:
        io: CliIO for output
        ctx: ElroyContext for config (show_confidence setting)
        diagnosis: The diagnosis result to display
    """
    # Header
    io.info("")
    io.info("═" * 60)
    io.info("  ERROR DIAGNOSED")
    io.info("═" * 60)
    io.info("")

    # User-friendly explanation
    io.info(diagnosis.user_explanation)
    io.info("")

    # Root cause (technical)
    io.info("ROOT CAUSE:")
    io.info(f"  {diagnosis.root_cause}")
    io.info("")

    # Suggested fixes
    if diagnosis.suggested_fixes:
        io.info("SUGGESTED FIXES:")
        io.info("")

        for i, fix in enumerate(diagnosis.suggested_fixes, 1):
            io.info(f"{i}. [{fix.fix_type.value.upper()}] {fix.description}")
            io.info("")
            io.info("   Instructions:")
            # Split instructions into lines and indent
            for line in fix.instructions.split("\n"):
                if line.strip():
                    io.info(f"   {line}")
            io.info("")

    # Confidence score (if enabled)
    show_confidence = getattr(ctx, "diagnosis_show_confidence", True)
    if show_confidence:
        confidence_pct = int(diagnosis.confidence * 100)
        io.info(f"Confidence: {confidence_pct}%")
        io.info("")

    # Restart suggestion
    io.info("After implementing a fix, please restart Elroy to verify.")
    io.info("═" * 60)
    io.info("")
