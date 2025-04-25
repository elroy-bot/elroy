"""
Memory service for ElroyContext.
"""

from datetime import timedelta


class MemoryService:
    """Provides memory-related functionality with lazy initialization"""

    def __init__(self, config):
        self.config = config

    @property
    def max_in_context_message_age(self) -> timedelta:
        minutes = self.config.max_context_age_minutes
        return timedelta(minutes=minutes if minutes is not None else 0)

    @property
    def min_convo_age_for_greeting(self) -> timedelta:
        minutes = self.config.min_convo_age_for_greeting_minutes
        return timedelta(minutes=minutes if minutes is not None else 0)
