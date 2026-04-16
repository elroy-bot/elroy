from collections.abc import Callable

from ...core.logging import get_logger
from ...db.db_models import UserPreference
from ...db.db_session import DbSession
from ...utils.utils import is_blank
from .store import UserPreferenceStore

logger = get_logger()


class UserPreferenceOrchestrator:
    def __init__(self, db: DbSession, user_id: int, refresh_system_instructions_fn: Callable[[], None]):
        self.db = db
        self.user_id = user_id
        self.refresh_system_instructions_fn = refresh_system_instructions_fn
        self.store = UserPreferenceStore(db, user_id)

    def get_or_create_user_preference(self) -> UserPreference:
        return self.store.get_or_create_user_preference()

    def set_assistant_name(self, assistant_name: str) -> str:
        user_preference = self.get_or_create_user_preference()
        user_preference.assistant_name = assistant_name
        self.db.add(user_preference)
        self.db.commit()
        self.refresh_system_instructions_fn()
        return f"Assistant name updated to {assistant_name}."

    def reset_system_persona(self) -> str:
        user_preference = self.get_or_create_user_preference()
        if not user_preference.system_persona:
            logger.warning("System persona was already set to default")

        user_preference.system_persona = None
        self.db.add(user_preference)
        self.db.commit()
        self.refresh_system_instructions_fn()
        return "System persona cleared, will now use default persona."

    def set_persona(self, system_persona: str) -> str:
        system_persona = system_persona.strip()
        if is_blank(system_persona):
            raise ValueError("System persona cannot be blank.")

        user_preference = self.get_or_create_user_preference()
        if user_preference.system_persona == system_persona:
            logger.info("New system persona and old system persona are identical")
            return "New system persona and old system persona are identical"

        user_preference.system_persona = system_persona
        self.db.add(user_preference)
        self.db.commit()
        self.refresh_system_instructions_fn()
        return "System persona updated."
