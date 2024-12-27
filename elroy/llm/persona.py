from ..config.constants import ASSISTANT_ALIAS_STRING, USER_ALIAS_STRING
from ..config.ctx import ElroyContext
from ..tools.user_preferences import get_or_create_user_preference


def get_persona(ctx: ElroyContext):
    user_preference = get_or_create_user_preference(ctx)
    if user_preference.system_persona:
        raw_persona = user_preference.system_persona
    else:
        raw_persona = ctx.default_persona

    if user_preference.preferred_name:
        user_noun = user_preference.preferred_name
    else:
        user_noun = "my user"
    return raw_persona.replace(USER_ALIAS_STRING, user_noun).replace(ASSISTANT_ALIAS_STRING, get_assistant_name(ctx))


def get_assistant_name(ctx: ElroyContext) -> str:
    if not ctx.user_id:
        return ctx.default_assistant_name
    else:
        user_preference = get_or_create_user_preference(ctx)
        if user_preference.assistant_name:
            return user_preference.assistant_name
        else:
            return ctx.default_assistant_name


def get_system_instruction_label(assistant_name: str) -> str:
    return f"*{assistant_name} System Instruction*"
