import inspect
from typing import Callable, Set

from rich.table import Table
from toolz import pipe
from toolz.curried import map

from ..cli.slash_commands import (
    add_internal_thought,
    contemplate,
    print_context_messages,
    print_system_instruction,
)
from ..core.constants import IS_ENABLED, user_only_tool
from ..core.ctx import ElroyContext
from ..repository.context_messages.operations import (
    pop,
    refresh_system_instructions,
    reset_messages,
    rewrite,
    save,
)
from ..repository.context_messages.tools import (
    add_goal_to_current_context,
    add_memory_to_current_context,
    drop_goal_from_current_context,
    drop_memory_from_current_context,
)
from ..repository.documents.tools import (
    get_document_excerpt,
    get_source_doc_metadata,
    get_source_documents,
    ingest_doc,
    reingest_doc,
)
from ..repository.goals.queries import print_active_goals, print_complete_goals
from ..repository.goals.tools import (
    add_goal_status_update,
    create_goal,
    delete_goal_permanently,
    mark_goal_completed,
    print_goal,
    rename_goal,
)
from ..repository.memories.operations import remember_convo
from ..repository.memories.tools import (
    create_memory,
    examine_memories,
    get_source_content_for_memory,
    print_memories,
    print_memory,
    search_memories,
    update_outdated_or_incorrect_memory,
)
from ..repository.recall.queries import search_documents
from ..repository.user.operations import set_assistant_name
from ..repository.user.tools import (
    get_user_full_name,
    get_user_preferred_name,
    set_user_full_name,
    set_user_preferred_name,
)
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
    update_outdated_or_incorrect_memory,
}
NON_ARG_PREFILL_COMMANDS: Set[Callable] = {
    get_source_content_for_memory,
    create_goal,
    create_memory,
    contemplate,
    examine_memories,
    get_user_full_name,
    set_user_full_name,
    search_documents,
    get_document_excerpt,
    get_source_doc_metadata,
    get_source_documents,
    get_user_preferred_name,
    set_user_preferred_name,
    tail_elroy_logs,
    make_coding_edit,
}
USER_ONLY_COMMANDS = {
    ingest_doc,
    reingest_doc,
    print_config,
    add_internal_thought,
    reset_messages,
    print_context_messages,
    print_system_instruction,
    pop,
    save,
    rewrite,
    refresh_system_instructions,
    print_active_goals,
    print_complete_goals,
    print_memories,
    search_memories,
    create_bug_report,
    set_assistant_name,
    remember_convo,
}
ASSISTANT_VISIBLE_COMMANDS: Set[Callable] = {
    f
    for f in (
        NON_ARG_PREFILL_COMMANDS
        | IN_CONTEXT_GOAL_COMMANDS
        | NON_CONTEXT_GOAL_COMMANDS
        | ALL_ACTIVE_GOAL_COMMANDS
        | IN_CONTEXT_MEMORY_COMMANDS
        | NON_CONTEXT_MEMORY_COMMANDS
        | ALL_ACTIVE_MEMORY_COMMANDS
    )
    if getattr(f, IS_ENABLED, True)
}

SYSTEM_COMMANDS = ASSISTANT_VISIBLE_COMMANDS | USER_ONLY_COMMANDS


@user_only_tool
def get_help(ctx: ElroyContext) -> Table:
    """Prints the available system commands

    Returns:
        str: The available system commands
    """

    commands = pipe(
        ctx.tool_registry.tools.values(),
        map(
            lambda f: (
                f.__name__,
                inspect.getdoc(f).split("\n")[0],  # type: ignore
            )
        ),
        list,
        sorted,
    )

    table = Table(title="Available Slash Commands")
    table.add_column("Command", justify="left", style="cyan", no_wrap=True)
    table.add_column("Description", justify="left", style="green")

    for command, description in commands:  # type: ignore
        table.add_row(command, description)
    return table
