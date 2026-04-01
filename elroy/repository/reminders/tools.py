from ...core.constants import RecoverableToolError, tool
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...utils.clock import string_to_datetime
from ...utils.utils import is_blank
from ..context_messages.operations import add_context_messages
from ..memories.transforms import to_fast_recall_tool_call
from ..tasks.operations import rename_task, update_task_text
from .operations import do_complete_due_item, do_create_due_item, do_delete_due_item
from .queries import get_active_due_item_names, get_db_due_item_by_name

logger = get_logger()


@tool
def create_due_item(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time: str | None = None,
    trigger_context: str | None = None,
) -> str:
    """Creates a due item that can be triggered by time and/or context.

    Args:
        name (str): Name of the due item (must be unique)
        text (str): The item text to display when triggered
        trigger_time (Optional[str]): When the item should trigger in format "YYYY-MM-DD HH:MM" (e.g., "2024-12-25 09:00"). If provided, creates a timed due item.
        trigger_context (Optional[str]): Description of the context/situation when this item should be triggered.

    Returns:
        str: A confirmation message that the due item was created.

    Raises:
        ValueError: If name is empty or if neither trigger_time nor trigger_context is provided

    Note:
        - You can provide trigger_time only (timed due item)
        - You can provide trigger_context only (context-triggered due item)
        - You can provide both trigger_time and trigger_context
        - You must provide at least one trigger
    """

    trigger_datetime = None
    if trigger_time:
        trigger_datetime = string_to_datetime(trigger_time)

    due_item = do_create_due_item(ctx, name, text, trigger_datetime, trigger_context)
    # Validation
    if is_blank(name):
        raise ValueError("Due item name cannot be empty")

    if trigger_datetime and trigger_context:
        f"New due item created: '{name}' - Timed: {trigger_datetime.strftime('%Y-%m-%d %H:%M:%S')}, Context: {trigger_context}"
    elif trigger_datetime:
        f"New timed due item created: '{name}' at {trigger_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        pass

    add_context_messages(ctx, to_fast_recall_tool_call(due_item))

    if trigger_time and trigger_context:
        return f"Hybrid due item '{name}' has been created for {trigger_time} and context: {trigger_context}."
    if trigger_time:
        return f"Timed due item '{name}' has been created for {trigger_time}."
    return f"Contextual due item '{name}' has been created."


@tool
def complete_due_item(ctx: ElroyContext, name: str, closing_comment: str | None = None) -> str:
    """Marks a due item as completed.

    Args:
        name (str): The name of the due item to mark complete
        closing_comment (Optional[str]): Optional comment on why the item was completed

    Returns:
        str: Confirmation message that the item was completed
    """
    return do_complete_due_item(ctx, name, closing_comment)


@tool
def delete_due_item(ctx: ElroyContext, name: str, closing_comment: str | None = None) -> str:
    """Permanently deletes a due item.

    Args:
        name (str): The name of the due item to delete
        closing_comment (Optional[str]): Optional comment on why the item was deleted

    Returns:
        str: Confirmation message that the item was deleted
    """
    return do_delete_due_item(ctx, name, closing_comment)


@tool
def rename_due_item(ctx: ElroyContext, old_name: str, new_name: str) -> str:
    """Renames an existing due item.

    Args:
        old_name (str): The current name of the item
        new_name (str): The new name for the item

    Returns:
        str: A confirmation message that the item was renamed

    Raises:
        Exception: If the item with old_name doesn't exist or new_name already exists
    """
    old_due_item = get_db_due_item_by_name(ctx, old_name)

    if not old_due_item:
        active_names = get_active_due_item_names(ctx)
        raise Exception(f"Active due item '{old_name}' not found for user {ctx.user_id}. Active items: " + ", ".join(active_names))

    existing_due_item_with_new_name = get_db_due_item_by_name(ctx, new_name)

    if existing_due_item_with_new_name:
        raise Exception(f"Active due item '{new_name}' already exists for user {ctx.user_id}")

    rename_task(ctx, old_name, new_name)

    return f"Due item '{old_name}' has been renamed to '{new_name}'."


@tool
def print_due_item(ctx: ElroyContext, name: str) -> str:
    """Prints the due item with the given name.

    Args:
        name (str): Name of the due item to retrieve

    Returns:
        str: The item's details if found, or an error message if not found
    """
    due_item = get_db_due_item_by_name(ctx, name)
    if due_item:
        details = [f"Due item '{name}':"]

        if due_item.trigger_datetime:
            trigger_time = due_item.trigger_datetime.strftime("%Y-%m-%d %H:%M:%S")
            details.append(f"Trigger Time: {trigger_time}")

        if due_item.trigger_context:
            details.append(f"Context: {due_item.trigger_context}")

        details.append(f"Text: {due_item.text}")

        return "\n".join(details)
    valid_due_items = ",".join(sorted(get_active_due_item_names(ctx)))
    raise RecoverableToolError(f"Due item '{name}' not found. Valid items: {valid_due_items}")


@tool
def update_due_item_text(ctx: ElroyContext, name: str, new_text: str) -> str:
    """Updates the text of an existing due item.

    Args:
        name (str): Name of the item to update
        new_text (str): The new item text

    Returns:
        str: Confirmation message that the item was updated

    Raises:
        RecoverableToolError: If the item doesn't exist
    """
    due_item = get_db_due_item_by_name(ctx, name)
    if not due_item:
        valid_due_items = ",".join(sorted(get_active_due_item_names(ctx)))
        raise RecoverableToolError(f"Due item '{name}' not found. Valid items: {valid_due_items}")

    update_task_text(ctx, name, new_text)

    return f"Due item '{name}' text has been updated."
