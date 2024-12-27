from typing import Optional

from ..config.config import ElroyConfig
from ..config.constants import ASSISTANT_ALIAS_STRING, USER_ALIAS_STRING
from ..db.db_manager import DbManager
from ..tools.user_preferences import get_or_create_user_preference


def get_persona(db: DbManager, config: ElroyConfig, user_id: Optional[int]):
    if not user_id:
        user_noun = "my user"
        raw_persona = config.default_persona
    else:
        user_preference = get_or_create_user_preference(db, user_id)
        if user_preference.system_persona:
            raw_persona = user_preference.system_persona
        else:
            raw_persona = config.default_persona

        if user_preference.preferred_name:
            user_noun = user_preference.preferred_name
        else:
            user_noun = "my user"
    return raw_persona.replace(USER_ALIAS_STRING, user_noun).replace(ASSISTANT_ALIAS_STRING, get_assistant_name(db, config, user_id))


def get_assistant_name(db: DbManager, config: ElroyConfig, user_id: Optional[int]) -> str:
    if not user_id:
        return config.default_assistant_name
    else:
        user_preference = get_or_create_user_preference(db, user_id)
        if user_preference.assistant_name:
            return user_preference.assistant_name
        else:
            return config.default_assistant_name


def get_system_instruction_label(assistant_name: str) -> str:
    return f"*{assistant_name} System Instruction*"
