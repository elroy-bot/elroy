import inspect
from typing import Callable, Set

from rich.table import Table
from toolz import concatv, pipe
from toolz.curried import map

from ..cli.slash_commands import (
    add_internal_thought,
    memo,
    print_context_messages,
    print_system_instruction,
)
from ..core.constants import IS_ENABLED, user_only_tool
from ..core.ctx import ElroyContext
from ..repository.background_ingestion.tools import (
    disable_background_ingestion,
    get_background_ingestion_status,
    remove_background_ingestion,
    setup_background_ingestion,
    update_background_ingestion,
)
from ..repository.context_messages.operations import (
    pop,
    refresh_system_instructions,
    reset_messages,
    rewrite,
    save,
)
from ..repository.context_messages.tools import (
    add_memory_to_current_context,
    drop_memory_from_current_context,
)
from ..repository.documents.tools import (
    get_document_excerpt,
    get_source_doc_metadata,
    get_source_documents,
    ingest_doc,
    reingest_doc,
)
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
from ..repository.reminders.queries import (
    print_active_reminders,
    print_inactive_reminders,
)
from ..repository.reminders.tools import (
    complete_reminder,
    create_reminder,
    delete_reminder,
    print_reminder,
    rename_reminder,
    update_reminder_text,
)
from ..repository.user.operations import set_assistant_name
from ..repository.user.tools import (
    get_user_full_name,
    get_user_preferred_name,
    set_user_full_name,
    set_user_preferred_name,
)
from .developer import (
    create_bug_report,
    print_config,
    tail_elroy_logs,
)

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
ALL_ACTIVE_REMINDER_COMMANDS: Set[Callable] = {
    delete_reminder,
    complete_reminder,
    print_reminder,
    rename_reminder,
    update_reminder_text,
}
NON_ARG_PREFILL_COMMANDS: Set[Callable] = {
    get_source_content_for_memory,
    create_reminder,
    create_memory,
    examine_memories,
    get_user_full_name,
    set_user_full_name,
    search_documents,
    get_document_excerpt,
    get_source_doc_metadata,
    get_source_documents,
    get_user_preferred_name,
    set_user_preferred_name,
    setup_background_ingestion,
    update_background_ingestion,
    get_background_ingestion_status,
    disable_background_ingestion,
    remove_background_ingestion,
}
USER_ONLY_COMMANDS = {
    tail_elroy_logs,
    ingest_doc,
    reingest_doc,
    print_config,
    add_internal_thought,
    memo,
    reset_messages,
    print_context_messages,
    print_system_instruction,
    pop,
    save,
    rewrite,
    refresh_system_instructions,
    print_memories,
    search_memories,
    print_active_reminders,
    print_inactive_reminders,
    create_bug_report,
    set_assistant_name,
}
ASSISTANT_VISIBLE_COMMANDS: Set[Callable] = {
    f
    for f in (
        NON_ARG_PREFILL_COMMANDS
        | IN_CONTEXT_MEMORY_COMMANDS
        | NON_CONTEXT_MEMORY_COMMANDS
        | ALL_ACTIVE_MEMORY_COMMANDS
        | ALL_ACTIVE_REMINDER_COMMANDS
    )
    if getattr(f, IS_ENABLED, True)
}


@user_only_tool
def get_help(ctx: ElroyContext) -> Table:
    """Prints the available system commands

    Returns:
        str: The available system commands
    """

    commands = pipe(
        concatv(ctx.tool_registry.tools.values(), USER_ONLY_COMMANDS),
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
