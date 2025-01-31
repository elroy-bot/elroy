from typing import Callable, Set

from ..cli.slash_commands import (
    add_internal_thought,
    contemplate,
    help,
    print_context_messages,
    print_system_instruction,
)
from ..repository.context_messages.operations import (
    add_goal_to_current_context,
    add_memory_to_current_context,
    drop_goal_from_current_context,
    drop_memory_from_current_context,
    refresh_system_instructions,
    reset_messages,
)
from ..repository.goals.operations import (
    add_goal_status_update,
    create_goal,
    delete_goal_permanently,
    mark_goal_completed,
    rename_goal,
)
from ..repository.goals.queries import print_goal
from ..repository.memories.operations import create_memory, remember_convo
from ..repository.memories.queries import print_memory, query_memory
from ..repository.user.operations import (
    set_assistant_name,
    set_user_full_name,
    set_user_preferred_name,
)
from ..repository.user.queries import get_user_full_name, get_user_preferred_name
from .developer import (
    create_bug_report,
    make_coding_edit,
    print_config,
    tail_elroy_logs,
)

IN_CONTEXT_GOAL_COMMANDS: Set[Callable] = {
    drop_goal_from_current_context,
}
NON_CONTEXT_GOAL_COMMANDS: Set[Callable] = {
    add_goal_to_current_context,
}
ALL_ACTIVE_GOAL_COMMANDS: Set[Callable] = {
    rename_goal,
    print_goal,
    add_goal_status_update,
    mark_goal_completed,
    delete_goal_permanently,
}
IN_CONTEXT_MEMORY_COMMANDS: Set[Callable] = {
    drop_memory_from_current_context,
}
NON_CONTEXT_MEMORY_COMMANDS: Set[Callable] = {
    add_memory_to_current_context,
}
ALL_ACTIVE_MEMORY_COMMANDS: Set[Callable] = {
    print_memory,
}
NON_ARG_PREFILL_COMMANDS: Set[Callable] = {
    create_goal,
    create_memory,
    contemplate,
    query_memory,
    get_user_full_name,
    set_user_full_name,
    get_user_preferred_name,
    set_user_preferred_name,
    tail_elroy_logs,
    make_coding_edit,
}
USER_ONLY_COMMANDS = {
    print_config,
    add_internal_thought,
    reset_messages,
    print_context_messages,
    print_system_instruction,
    refresh_system_instructions,
    help,
    create_bug_report,
    set_assistant_name,
    remember_convo,
}
ASSISTANT_VISIBLE_COMMANDS: Set[Callable] = (
    NON_ARG_PREFILL_COMMANDS
    | IN_CONTEXT_GOAL_COMMANDS
    | NON_CONTEXT_GOAL_COMMANDS
    | ALL_ACTIVE_GOAL_COMMANDS
    | IN_CONTEXT_MEMORY_COMMANDS
    | NON_CONTEXT_MEMORY_COMMANDS
    | ALL_ACTIVE_MEMORY_COMMANDS
)
SYSTEM_COMMANDS = ASSISTANT_VISIBLE_COMMANDS | USER_ONLY_COMMANDS
