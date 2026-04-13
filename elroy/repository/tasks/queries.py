from ...core.services.task_service import TaskQueryService
from ...db.db_models import AgendaItem
from ...db.db_session import DbSession


def task_query_service(db: DbSession, user_id: int) -> TaskQueryService:
    return TaskQueryService(db, user_id)


def get_task_by_name(query_service: TaskQueryService, name: str) -> AgendaItem | None:
    return query_service.get_task_by_name(name)


def get_active_tasks(query_service: TaskQueryService) -> list[AgendaItem]:
    return query_service.get_active_tasks()


def get_triggered_tasks(query_service: TaskQueryService) -> list[AgendaItem]:
    return query_service.get_triggered_tasks()


def get_due_tasks(query_service: TaskQueryService) -> list[AgendaItem]:
    return query_service.get_due_tasks()


def get_today_tasks(query_service: TaskQueryService) -> list[AgendaItem]:
    return query_service.get_today_tasks()
