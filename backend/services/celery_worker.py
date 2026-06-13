from celery import Celery
from backend.core.config import settings

celery_app = Celery(
    "finagent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.services.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)