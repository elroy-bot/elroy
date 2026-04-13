from ...core.services.reminder_service import ReminderOperationService
from ...core.services.task_service import TaskOperationService
from ...db.db_session import DbSession


def reminder_operation_service(
    db: DbSession,
    user_id: int,
    *,
    task_operations: TaskOperationService | None = None,
) -> ReminderOperationService:
    return ReminderOperationService(db, user_id, task_operations=task_operations)


def create_onboarding_due_item(operation_service: ReminderOperationService, preferred_name: str) -> None:
    operation_service.create_onboarding_due_item(preferred_name)


def do_create_due_item(
    operation_service: ReminderOperationService,
    name: str,
    text: str,
    trigger_time=None,
    trigger_context=None,
):
    return operation_service.create_due_item(
        name=name,
        text=text,
        trigger_time=trigger_time,
        trigger_context=trigger_context,
    )


def do_complete_due_item(operation_service: ReminderOperationService, item_name: str, closing_comment: str | None = None) -> str:
    return operation_service.complete_due_item(item_name, closing_comment)


def do_delete_due_item(operation_service: ReminderOperationService, item_name: str, closing_comment: str | None = None) -> str:
    return operation_service.delete_due_item(item_name, closing_comment)
