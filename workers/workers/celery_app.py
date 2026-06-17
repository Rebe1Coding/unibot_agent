from celery import Celery

from workers.config import settings

app = Celery(
    "workers",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    # Лимиты на время выполнения задачи
    task_soft_time_limit=300,  # 5 минут — мягкий лимит (SoftTimeLimitExceeded)
    task_time_limit=360,  # 6 минут — жёсткий kill
)

app.autodiscover_tasks(["workers.tasks"])
