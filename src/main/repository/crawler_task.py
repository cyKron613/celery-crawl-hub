import datetime

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import load_only
from sqlalchemy.orm.attributes import set_committed_value

from src.main.config.manager import settings
from src.main.core.orm.repository.base import BaseRepository
from src.main.models.crawler_result import ExShippingInformation
from src.main.models.crawler_task import CrawlerTask, CrawlerTaskExecution


class CrawlerTaskRepository(BaseRepository):
    @staticmethod
    def _execution_load_only_fields(include_inserted_article_ids: bool):
        fields = [
            CrawlerTaskExecution.id,
            CrawlerTaskExecution.task_id,
            CrawlerTaskExecution.trigger_type,
            CrawlerTaskExecution.status,
            CrawlerTaskExecution.celery_task_id,
            CrawlerTaskExecution.started_at,
            CrawlerTaskExecution.finished_at,
            CrawlerTaskExecution.result_count,
            CrawlerTaskExecution.error_message,
            CrawlerTaskExecution.result_preview,
            CrawlerTaskExecution.created_at,
        ]
        if include_inserted_article_ids:
            fields.append(CrawlerTaskExecution.inserted_article_ids)
        return load_only(*fields)

    async def has_inserted_article_ids_column(self) -> bool:
        stmt = text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema_name
              AND table_name = 'crawler_task_executions'
              AND column_name = 'inserted_article_ids'
            LIMIT 1
            """
        )
        result = await self.async_session.execute(stmt, {"schema_name": settings.POSTGRES_SCHEMA})
        return result.scalar_one_or_none() is not None

    async def get_shipping_result_columns(self) -> list[str]:
        stmt = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema_name
              AND table_name = 'ex_shipping_information'
            ORDER BY ordinal_position
            """
        )
        result = await self.async_session.execute(stmt, {"schema_name": settings.POSTGRES_SCHEMA})
        return [row[0] for row in result.fetchall()]

    @staticmethod
    def _hydrate_missing_inserted_article_ids(execution: CrawlerTaskExecution | None) -> CrawlerTaskExecution | None:
        if execution is not None and "inserted_article_ids" not in execution.__dict__:
            set_committed_value(execution, "inserted_article_ids", None)
        return execution

    async def create_task(self, task: CrawlerTask) -> CrawlerTask:
        self.async_session.add(task)
        await self.async_session.commit()
        await self.async_session.refresh(task)
        return task

    async def get_task_by_id(self, task_id: str) -> CrawlerTask | None:
        result = await self.async_session.execute(select(CrawlerTask).where(CrawlerTask.id == task_id))
        return result.scalar_one_or_none()

    async def get_task_by_name(self, task_name: str) -> CrawlerTask | None:
        result = await self.async_session.execute(select(CrawlerTask).where(CrawlerTask.task_name == task_name))
        return result.scalar_one_or_none()

    async def count_tasks(self) -> int:
        result = await self.async_session.execute(select(func.count()).select_from(CrawlerTask))
        return int(result.scalar_one() or 0)

    async def list_tasks(self, page: int = 1, page_size: int = 20) -> list[CrawlerTask]:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        offset = (safe_page - 1) * safe_page_size
        result = await self.async_session.execute(
            select(CrawlerTask)
            .order_by(CrawlerTask.updated_at.desc(), CrawlerTask.created_at.desc())
            .offset(offset)
            .limit(safe_page_size)
        )
        return list(result.scalars().all())

    async def delete_task(self, task: CrawlerTask) -> None:
        await self.async_session.delete(task)
        await self.async_session.commit()

    async def save_task(self, task: CrawlerTask) -> CrawlerTask:
        self.async_session.add(task)
        await self.async_session.commit()
        await self.async_session.refresh(task)
        return task

    async def create_execution(self, execution: CrawlerTaskExecution) -> CrawlerTaskExecution:
        self.async_session.add(execution)
        await self.async_session.commit()
        await self.async_session.refresh(execution, attribute_names=["id", "task_id", "trigger_type", "status", "celery_task_id", "started_at", "finished_at", "result_count", "error_message", "result_preview", "created_at"])
        return execution

    async def save_execution(self, execution: CrawlerTaskExecution) -> CrawlerTaskExecution:
        self.async_session.add(execution)
        await self.async_session.commit()
        include_inserted_article_ids = await self.has_inserted_article_ids_column()
        attribute_names = ["id", "task_id", "trigger_type", "status", "celery_task_id", "started_at", "finished_at", "result_count", "error_message", "result_preview", "created_at"]
        if include_inserted_article_ids:
            attribute_names.append("inserted_article_ids")
        await self.async_session.refresh(execution, attribute_names=attribute_names)
        self._hydrate_missing_inserted_article_ids(execution)
        return execution

    async def get_execution_by_id(self, execution_id: str) -> CrawlerTaskExecution | None:
        include_inserted_article_ids = await self.has_inserted_article_ids_column()
        stmt: Select = (
            select(CrawlerTaskExecution)
            .options(self._execution_load_only_fields(include_inserted_article_ids))
            .where(CrawlerTaskExecution.id == execution_id)
        )
        result = await self.async_session.execute(stmt)
        return self._hydrate_missing_inserted_article_ids(result.scalar_one_or_none())

    async def get_execution_by_celery_task_id(self, celery_task_id: str) -> CrawlerTaskExecution | None:
        include_inserted_article_ids = await self.has_inserted_article_ids_column()
        stmt: Select = (
            select(CrawlerTaskExecution)
            .options(self._execution_load_only_fields(include_inserted_article_ids))
            .where(CrawlerTaskExecution.celery_task_id == celery_task_id)
            .order_by(CrawlerTaskExecution.started_at.desc(), CrawlerTaskExecution.created_at.desc())
            .limit(1)
        )
        result = await self.async_session.execute(stmt)
        return self._hydrate_missing_inserted_article_ids(result.scalar_one_or_none())

    async def list_executions(self, task_id: str, limit: int) -> list[CrawlerTaskExecution]:
        include_inserted_article_ids = await self.has_inserted_article_ids_column()
        stmt: Select = (
            select(CrawlerTaskExecution)
            .options(self._execution_load_only_fields(include_inserted_article_ids))
            .where(CrawlerTaskExecution.task_id == task_id)
            .order_by(CrawlerTaskExecution.started_at.desc(), CrawlerTaskExecution.created_at.desc())
            .limit(limit)
        )
        result = await self.async_session.execute(stmt)
        executions = list(result.scalars().all())
        for execution in executions:
            self._hydrate_missing_inserted_article_ids(execution)
        return executions

    async def list_shipping_results_by_article_ids(self, article_ids: list[str]) -> list[dict]:
        if not article_ids:
            return []

        existing_columns = await self.get_shipping_result_columns()
        if not existing_columns:
            return []

        select_columns = ", ".join(existing_columns)
        stmt = text(
            f"SELECT {select_columns} FROM {settings.POSTGRES_SCHEMA}.ex_shipping_information WHERE article_id = ANY(:article_ids)"
        )
        result = await self.async_session.execute(stmt, {"article_ids": article_ids})
        rows = [dict(row._mapping) for row in result.fetchall()]
        article_id_order = {article_id: index for index, article_id in enumerate(article_ids)}
        return sorted(rows, key=lambda item: article_id_order.get(item.get("article_id"), len(article_id_order)))

    async def count_shipping_results(self) -> int:
        result = await self.async_session.execute(select(func.count()).select_from(ExShippingInformation))
        return int(result.scalar_one() or 0)

    async def list_shipping_results(self, page: int = 1, page_size: int = 20) -> list[ExShippingInformation]:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        offset = (safe_page - 1) * safe_page_size
        result = await self.async_session.execute(
            select(ExShippingInformation)
            .order_by(
                ExShippingInformation.update_time.desc(),
                ExShippingInformation.detail_date.desc(),
                ExShippingInformation.article_id.desc(),
            )
            .offset(offset)
            .limit(safe_page_size)
        )
        return list(result.scalars().all())

    async def list_due_tasks(self, due_before: datetime.datetime) -> list[CrawlerTask]:
        stmt = (
            select(CrawlerTask)
            .where(CrawlerTask.schedule_enabled.is_(True))
            .where(CrawlerTask.next_run_at.is_not(None))
            .where(CrawlerTask.next_run_at <= due_before)
        )
        result = await self.async_session.execute(stmt)
        return list(result.scalars().all())