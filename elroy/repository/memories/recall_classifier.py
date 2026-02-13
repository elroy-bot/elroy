"""Classifier to determine if memory recall is necessary for a message.

This module implements a two-stage hybrid approach:
1. Fast heuristics for obvious cases (greetings, acknowledgments)
2. LLM-based classification for nuanced cases

The classifier helps reduce latency by skipping unnecessary memory recall.
"""

from pydantic import BaseModel

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...repository.context_messages.data_models import ContextMessage
from .queries import get_message_content

logger = get_logger()


class MemoryRecallDecision(BaseModel):
    """Decision on whether memory recall is necessary for this message."""

    needs_recall: bool
    reasoning: str


def should_recall_memory(
    ctx: ElroyContext,
    current_message: str,
    recent_messages: list[ContextMessage],
) -> MemoryRecallDecision:
    """Determine if memory recall is necessary for the current message.

    Uses a two-stage approach:
    1. Fast heuristics for obvious cases
    2. LLM-based classification for nuanced cases

    Args:
        ctx: ElroyContext for config and LLM access
        current_message: The user's current message
        recent_messages: Recent messages for context

    Returns:
        MemoryRecallDecision with needs_recall bool and reasoning
    """
    # Stage 1: Fast heuristics
    heuristic_result = _apply_heuristics(current_message)
    if heuristic_result is not None:
        return heuristic_result

    # Stage 2: LLM-based classification
    return _classify_with_llm(ctx, current_message, recent_messages)


def _apply_heuristics(message: str) -> MemoryRecallDecision | None:
    """Apply fast heuristics to determine if recall is obviously not needed.

    Returns None if uncertain (needs LLM classification).

    Args:
        message: The message to analyze

    Returns:
        MemoryRecallDecision if confident, None if uncertain
    """
    message_lower = message.strip().lower()

    # Very short messages (likely acknowledgments)
    if len(message.strip()) < 10:
        common_short = [
            "ok",
            "okay",
            "yes",
            "no",
            "thanks",
            "thank you",
            "sure",
            "got it",
            "k",
            "yep",
            "nope",
        ]
        if message_lower in common_short:
            return MemoryRecallDecision(needs_recall=False, reasoning="Simple acknowledgment detected by heuristic")

    # Simple greetings (only if they're the entire message)
    greetings = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "goodbye",
        "bye",
    ]
    if message_lower in greetings:
        return MemoryRecallDecision(needs_recall=False, reasoning="Simple greeting detected by heuristic")

    # For any other message (especially those with specific topics/activities),
    # defer to LLM classifier to be conservative
    return None


def _classify_with_llm(
    ctx: ElroyContext,
    current_message: str,
    recent_messages: list[ContextMessage],
) -> MemoryRecallDecision:
    """Use fast_llm to classify if memory recall is needed.

    Args:
        ctx: ElroyContext for config and LLM access
        current_message: The current message
        recent_messages: Recent messages for context

    Returns:
        MemoryRecallDecision from fast_llm
    """
    # Build conversation context using existing utility
    # Get last N messages based on config
    window_size = ctx.memory_config.memory_recall_classifier_window
    context_window = recent_messages[-window_size:] if len(recent_messages) > window_size else recent_messages

    # Use existing get_message_content utility to format messages
    conversation_context = get_message_content(context_window, window_size)

    prompt = f"""Analyze if this message requires recalling information from long-term memory (including reminders).

Recent conversation:
{conversation_context}

Current message: {current_message}

Memory recall is NEEDED if (almost always):
- Message mentions ANY specific topic, activity, person, place, or thing
- Message references ANY past topics, events, or context
- Message contains substantive content beyond pure acknowledgment
- Message mentions activities, hobbies, tasks, or appointments that commonly have reminders
- Message is a follow-up question or statement
- Message asks about preferences, goals, or history
- When in doubt - ALWAYS prefer recall

Memory recall is NOT needed ONLY if:
- Message is ONLY a simple greeting with no other content (hi, hello, bye)
- Message is ONLY a simple acknowledgment with no other content (ok, thanks, yes, no)
- Message is ONLY a clarification question with no topic content (what?, huh?)

CRITICAL: If the message mentions ANY topic, activity, or substantive content, memory recall is NEEDED because there may be relevant reminders or memories. Be VERY conservative - prefer false positives over false negatives.

Analyze and decide if long-term memory recall is necessary."""

    system_message = "You are a classifier that determines if memory recall is necessary. Be VERY conservative - almost always enable recall unless the message is a pure acknowledgment/greeting with zero topic content. Missing a relevant reminder is worse than doing unnecessary recall."

    decision = ctx.fast_llm.query_llm_with_response_format(
        prompt=prompt,
        system=system_message,
        response_format=MemoryRecallDecision,
    )

    logger.debug(f"Memory recall classifier decision: {decision.needs_recall}, reasoning: {decision.reasoning}")

    return decision
