from celery import Celery

from elroy.config import get_config

# Avoid module-level project dependencies, so we can enqueue tasks in other parts of the codebase


# Initialize Celery
app = Celery("elroy", broker=get_config().redis_url)
app.conf.update(
    result_backend=get_config().redis_url,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)


# TODO: Some kind of system health check which ensures consistency
# - all context message sets begin with a system message
# - all embedding fields are populated


from elroy.config import is_production_env

if is_production_env():
    # autodiscover cloud tasks
    app.autodiscover_tasks(["elroy.env.cloud"], force=True)
