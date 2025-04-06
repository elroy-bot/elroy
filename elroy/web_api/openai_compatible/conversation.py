"""
Conversation tracking for the OpenAI-compatible API server.

This module handles tracking conversations, detecting divergence, and storing
messages in the database.
"""

import json
from typing import List, Optional, Tuple

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...repository.context_messages.data_models import ContextMessage
from ...repository.context_messages.queries import get_or_create_context_message_set
from ...repository.context_messages.transforms import context_message_to_db_message
from ..openai_compatible.memory import convert_openai_message_to_context_message
from ..openai_compatible.models import Message as OpenAIMessage

logger = get_logger()


class ConversationTracker:
    """
    Tracks conversations and handles divergence detection.

    This class implements position-based message comparison to detect when a
    conversation diverges from its stored history.
    """

    def __init__(self, ctx: ElroyContext):
        """Initialize the conversation tracker."""
        self.ctx = ctx
        self.context_message_set = get_or_create_context_message_set(ctx)

    def get_stored_messages(self) -> List[ContextMessage]:
        """Get the stored messages for the current conversation."""
        return self.context_message_set.messages_list

    def compare_and_update_conversation(self, messages: List[OpenAIMessage]) -> Tuple[List[ContextMessage], bool]:
        """
        Compare incoming messages with stored messages and update if divergence is detected.

        Args:
            messages: The incoming messages from the API request

        Returns:
            A tuple of (context_messages, diverged) where:
            - context_messages is the list of context messages to use for the response
            - diverged is True if the conversation diverged from the stored history
        """
        stored_messages = self.get_stored_messages()

        # Convert incoming messages to context messages
        incoming_context_messages = [convert_openai_message_to_context_message(msg, self.ctx.chat_model.name) for msg in messages]

        # If there are no stored messages, store all incoming messages
        if not stored_messages:
            self._store_messages(incoming_context_messages)
            return incoming_context_messages, False

        # Compare messages position by position
        divergence_index = self._find_divergence_index(stored_messages, incoming_context_messages)

        if divergence_index is None:
            # No divergence, but there might be new messages to append
            if len(incoming_context_messages) > len(stored_messages):
                new_messages = incoming_context_messages[len(stored_messages) :]
                self._append_messages(new_messages)
                return incoming_context_messages, False
            return stored_messages, False

        # Divergence detected, update stored messages
        logger.info(f"Conversation diverged at position {divergence_index}")
        new_messages = incoming_context_messages[divergence_index:]
        self._update_messages_after_divergence(divergence_index, new_messages)

        # Return the updated context messages
        return self.get_stored_messages(), True

    def _find_divergence_index(self, stored_messages: List[ContextMessage], incoming_messages: List[ContextMessage]) -> Optional[int]:
        """
        Find the index where the incoming messages diverge from the stored messages.

        Args:
            stored_messages: The stored messages
            incoming_messages: The incoming messages

        Returns:
            The index of the first divergent message, or None if no divergence is found
        """
        min_length = min(len(stored_messages), len(incoming_messages))

        for i in range(min_length):
            stored = stored_messages[i]
            incoming = incoming_messages[i]

            # Compare role and content
            if stored.role != incoming.role or stored.content != incoming.content:
                return i

        # No divergence found in the overlapping messages
        return None

    def _store_messages(self, messages: List[ContextMessage]) -> None:
        """
        Store a list of messages in the database.

        Args:
            messages: The messages to store
        """
        db_messages = []
        message_ids = []

        for msg in messages:
            db_message = context_message_to_db_message(self.ctx.user_id, msg)
            self.ctx.db.add(db_message)
            self.ctx.db.commit()
            self.ctx.db.refresh(db_message)

            db_messages.append(db_message)
            message_ids.append(db_message.id)

        # Update the context message set with the new message IDs
        self.context_message_set.context_message_set.message_ids = json.dumps(message_ids)
        self.ctx.db.add(self.context_message_set.context_message_set)
        self.ctx.db.commit()

    def _append_messages(self, messages: List[ContextMessage]) -> None:
        """
        Append messages to the existing conversation.

        Args:
            messages: The messages to append
        """
        db_messages = []
        message_ids = json.loads(self.context_message_set.context_message_set.message_ids)

        for msg in messages:
            db_message = context_message_to_db_message(self.ctx.user_id, msg)
            self.ctx.db.add(db_message)
            self.ctx.db.commit()
            self.ctx.db.refresh(db_message)

            db_messages.append(db_message)
            message_ids.append(db_message.id)

        # Update the context message set with the new message IDs
        self.context_message_set.context_message_set.message_ids = json.dumps(message_ids)
        self.ctx.db.add(self.context_message_set.context_message_set)
        self.ctx.db.commit()

    def _update_messages_after_divergence(self, divergence_index: int, new_messages: List[ContextMessage]) -> None:
        """
        Update the stored messages after a divergence is detected.

        This method:
        1. Keeps messages before the divergence point
        2. Discards messages after the divergence point
        3. Adds the new messages from the divergence point onward

        Args:
            divergence_index: The index where divergence was detected
            new_messages: The new messages to store from the divergence point onward
        """
        # Get the current message IDs
        message_ids = json.loads(self.context_message_set.context_message_set.message_ids)

        # Keep only the message IDs before the divergence
        message_ids = message_ids[:divergence_index]

        # Add the new messages
        db_messages = []
        for msg in new_messages:
            db_message = context_message_to_db_message(self.ctx.user_id, msg)
            self.ctx.db.add(db_message)
            self.ctx.db.commit()
            self.ctx.db.refresh(db_message)

            db_messages.append(db_message)
            message_ids.append(db_message.id)

        # Update the context message set with the new message IDs
        self.context_message_set.context_message_set.message_ids = json.dumps(message_ids)
        self.ctx.db.add(self.context_message_set.context_message_set)
        self.ctx.db.commit()
