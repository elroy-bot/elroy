"""
User service for ElroyContext.
"""

from functools import cached_property


class UserService:
    """Provides user-related functionality with lazy initialization"""

    def __init__(self, config, db_service):
        self.config = config
        self.db_service = db_service
        self._user_id = None

    @cached_property
    def user_id(self) -> int:
        """Get user ID, creating it if it doesn't exist."""
        # Import here to avoid circular imports
        from ...repository.user.operations import create_user_id
        from ...repository.user.queries import get_user_id_if_exists

        return get_user_id_if_exists(self.db_service.db, self.config.user_token) or create_user_id(
            self.db_service.db, self.config.user_token
        )
