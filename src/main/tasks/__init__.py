"""Celery tasks package.

Import task modules here so Celery autodiscover can register task decorators.
"""

from src.main.tasks import crawler_tasks  # noqa: F401
from src.main.tasks import translate_tasks  # noqa: F401
