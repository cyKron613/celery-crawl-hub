from datetime import timedelta

from celery import Celery
from kombu import Queue
from celery.signals import setup_logging, worker_process_init

from src.main.config.manager import settings
from src.main.config.handler.loguru_handler import configure_loguru_for_worker


celery_app = Celery(
    "crawler_studio",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=False,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_max_tasks_per_child = 50,  # 每个worker处理50个任务后重启
    worker_max_memory_per_child = 1200000,  # 限制worker内存使用(1200MB)
    result_expires = 86400, # 结果后端24小时过期 只采集不审计

    task_acks_late = False,  # 不重新排队 （如果失败较多就会导致阻塞）
    task_reject_on_worker_lost = False,  # Worker 丢失时不将任务重新放入队列
    task_publish_retry = False,        # 发布任务失败时不重试

    broker_pool_limit=settings.CELERY_BROKER_POOL_LIMIT,
    broker_connection_timeout=settings.CELERY_BROKER_CONNECTION_TIMEOUT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_default_queue="celery",
    task_queues=(
        Queue("celery"),
        Queue("translate_schedule"),
    ),
    task_routes={
        "translate_tasks.time_task": {"queue": "translate_schedule"},
    },
    
    beat_schedule={
        "dispatch-due-crawler-tasks": {
            "task": "crawler.dispatch_due_tasks",
            "schedule": timedelta(seconds=settings.CRAWLER_SCHEDULER_SCAN_SECONDS),
        },
        "dispatch-due-translate-tasks": {
            "task": "translate_tasks.time_task",
            "schedule": timedelta(seconds=settings.TRANSLATE_SCHEDULER_SCAN_SECONDS),
        },
    },
)


@setup_logging.connect
def on_celery_setup_logging(*args, **kwargs):
    configure_loguru_for_worker()


@worker_process_init.connect
def on_worker_process_init(*args, **kwargs):
    configure_loguru_for_worker()

# 导入 tasks 包，触发其中对任务模块的聚合导入。
import src.main.tasks  # noqa: F401

# 自动发现 src.main 下的 tasks 包。
celery_app.autodiscover_tasks(["src.main"])