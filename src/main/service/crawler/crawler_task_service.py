from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import croniter
from fastapi import status

from src.main.config.manager import settings
from src.main.core.orm.service.base import BaseService
from src.main.models.crawler_task import CrawlerTask, CrawlerTaskExecution
from src.main.repository.crawler_task import CrawlerTaskRepository
from src.main.schema.crawler_task import (
    CrawlerExecutionListResponseVo,
    CrawlerExecutionResultData,
    CrawlerExecutionResultResponseVo,
    CrawlerInsertedDataListResponseVo,
    CrawlerTaskCreateRequest,
    CrawlerTaskDetailResponseVo,
    CrawlerTaskListResponseVo,
    CrawlerTaskRunResponseVo,
    CrawlerTaskScheduleActionResponseVo,
    CrawlerTaskUpdateRequest,
)
from src.main.tasks.crawler_tasks import execute_crawler_task


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrawlerTaskService(BaseService[CrawlerTaskRepository]):
    @staticmethod
    def _build_task_model(payload: CrawlerTaskCreateRequest) -> CrawlerTask:
        task = CrawlerTask(**payload.model_dump())
        if task.schedule_enabled:
            task.next_run_at = CrawlerTaskService._resolve_next_run_at(task.schedule_type, task.interval_seconds, task.cron_expression)
        else:
            task.next_run_at = None
        return task

    @staticmethod
    def _resolve_next_run_at(schedule_type: str, interval_seconds: int | None, cron_expression: str | None) -> datetime | None:
        now = _utcnow()
        if schedule_type == "manual":
            return None
        if schedule_type == "interval":
            return now + timedelta(seconds=interval_seconds or 0)
        if not cron_expression or not croniter.is_valid(cron_expression):
            raise ValueError("无效的 cron_expression")
        local_tz = ZoneInfo(settings.CELERY_TIMEZONE)
        local_now = now.astimezone(local_tz)
        next_local_run = croniter(cron_expression, local_now).get_next(datetime)
        if next_local_run.tzinfo is None:
            next_local_run = next_local_run.replace(tzinfo=local_tz)
        return next_local_run.astimezone(timezone.utc)

    async def create_task(self, payload: CrawlerTaskCreateRequest) -> CrawlerTaskDetailResponseVo:
        existing = await self.repo.get_task_by_name(payload.task_name)
        if existing:
            return CrawlerTaskDetailResponseVo(code=status.HTTP_400_BAD_REQUEST, message="任务名称已存在")
        task = self._build_task_model(payload)
        created = await self.repo.create_task(task)
        return CrawlerTaskDetailResponseVo(code=status.HTTP_201_CREATED, message="任务创建成功", data=created)

    async def list_tasks(self, page: int = 1, page_size: int = 20) -> CrawlerTaskListResponseVo:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        total = await self.repo.count_tasks()
        total_pages = (total + safe_page_size - 1) // safe_page_size if total > 0 else 0

        if total_pages > 0 and safe_page > total_pages:
            safe_page = total_pages

        tasks = await self.repo.list_tasks(page=safe_page, page_size=safe_page_size)
        return CrawlerTaskListResponseVo(
            code=status.HTTP_200_OK,
            message="获取成功",
            data=tasks,
            page=safe_page,
            page_size=safe_page_size,
            total=total,
            total_pages=total_pages,
        )

    async def get_task(self, task_id: str) -> CrawlerTaskDetailResponseVo:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return CrawlerTaskDetailResponseVo(code=status.HTTP_404_NOT_FOUND, message="任务不存在")
        return CrawlerTaskDetailResponseVo(code=status.HTTP_200_OK, message="获取成功", data=task)

    async def update_task(self, task_id: str, payload: CrawlerTaskUpdateRequest) -> CrawlerTaskDetailResponseVo:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return CrawlerTaskDetailResponseVo(code=status.HTTP_404_NOT_FOUND, message="任务不存在")

        # 仅在名称发生变化时进行重名校验，避免更新同一条记录时误判。
        new_task_name = (payload.task_name or "").strip()
        current_task_name = (task.task_name or "").strip()
        if new_task_name != current_task_name:
            same_name_task = await self.repo.get_task_by_name(new_task_name)
            if same_name_task and str(same_name_task.id) != str(task.id):
                return CrawlerTaskDetailResponseVo(code=status.HTTP_400_BAD_REQUEST, message="任务名称已存在")

        for field_name, field_value in payload.model_dump().items():
            setattr(task, field_name, field_value)

        if task.schedule_enabled:
            task.next_run_at = self._resolve_next_run_at(task.schedule_type, task.interval_seconds, task.cron_expression)
        else:
            task.next_run_at = None

        updated = await self.repo.save_task(task)
        return CrawlerTaskDetailResponseVo(code=status.HTTP_200_OK, message="任务更新成功", data=updated)

    async def delete_task(self, task_id: str) -> CrawlerTaskScheduleActionResponseVo:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return CrawlerTaskScheduleActionResponseVo(code=status.HTTP_404_NOT_FOUND, message="任务不存在")
        await self.repo.delete_task(task)
        return CrawlerTaskScheduleActionResponseVo(
            code=status.HTTP_200_OK,
            message="任务删除成功",
            data={"task_id": task_id, "deleted": True},
        )

    async def run_task(self, task_id: str) -> CrawlerTaskRunResponseVo:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return CrawlerTaskRunResponseVo(code=status.HTTP_404_NOT_FOUND, message="任务不存在")

        async_result = execute_crawler_task.delay(task_id=task_id, trigger_type="manual")
        execution = CrawlerTaskExecution(
            task_id=task_id,
            trigger_type="manual",
            status="pending",
            celery_task_id=async_result.id,
        )
        await self.repo.create_execution(execution)
        return CrawlerTaskRunResponseVo(
            code=status.HTTP_200_OK,
            message="任务已提交执行",
            data={"task_id": task_id, "celery_task_id": async_result.id},
        )

    async def start_schedule(self, task_id: str) -> CrawlerTaskScheduleActionResponseVo:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return CrawlerTaskScheduleActionResponseVo(code=status.HTTP_404_NOT_FOUND, message="任务不存在")
        if task.schedule_type == "manual":
            return CrawlerTaskScheduleActionResponseVo(code=status.HTTP_400_BAD_REQUEST, message="manual 类型任务不支持启动调度")

        task.schedule_enabled = True
        task.next_run_at = self._resolve_next_run_at(task.schedule_type, task.interval_seconds, task.cron_expression)
        await self.repo.save_task(task)
        return CrawlerTaskScheduleActionResponseVo(
            code=status.HTTP_200_OK,
            message="调度已启动",
            data={"task_id": task_id, "schedule_enabled": True, "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None},
        )

    async def pause_schedule(self, task_id: str) -> CrawlerTaskScheduleActionResponseVo:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return CrawlerTaskScheduleActionResponseVo(code=status.HTTP_404_NOT_FOUND, message="任务不存在")
        task.schedule_enabled = False
        task.next_run_at = None
        await self.repo.save_task(task)
        return CrawlerTaskScheduleActionResponseVo(
            code=status.HTTP_200_OK,
            message="调度已暂停",
            data={"task_id": task_id, "schedule_enabled": False, "next_run_at": None},
        )

    async def list_executions(self, task_id: str, limit: int) -> CrawlerExecutionListResponseVo:
        task = await self.repo.get_task_by_id(task_id)
        if not task:
            return CrawlerExecutionListResponseVo(code=status.HTTP_404_NOT_FOUND, message="任务不存在")
        executions = await self.repo.list_executions(task_id, max(1, min(limit, 100)))
        return CrawlerExecutionListResponseVo(code=status.HTTP_200_OK, message="获取成功", data=executions)

    async def get_execution_results(self, celery_task_id: str) -> CrawlerExecutionResultResponseVo:
        execution = await self.repo.get_execution_by_celery_task_id(celery_task_id)
        if not execution:
            return CrawlerExecutionResultResponseVo(code=status.HTTP_404_NOT_FOUND, message="执行记录不存在")

        inserted_article_ids = execution.inserted_article_ids or []
        fallback_from_preview = False
        if not inserted_article_ids and execution.result_preview:
            inserted_article_ids = [item.get("article_id") for item in execution.result_preview if item.get("article_id")]
            fallback_from_preview = True

        records = await self.repo.list_shipping_results_by_article_ids(inserted_article_ids)
        data = CrawlerExecutionResultData(
            execution_id=execution.id,
            task_id=execution.task_id,
            celery_task_id=execution.celery_task_id or celery_task_id,
            status=execution.status,
            error_message=execution.error_message,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            result_count=execution.result_count,
            inserted_article_ids=inserted_article_ids,
            records=records,
        )

        if execution.status == "running":
            return CrawlerExecutionResultResponseVo(code=status.HTTP_202_ACCEPTED, message="任务尚未执行完毕", data=data)
        if execution.status == "failed":
            error_suffix = f"，异常: {execution.error_message}" if execution.error_message else ""
            return CrawlerExecutionResultResponseVo(
                code=status.HTTP_200_OK,
                message=f"任务执行失败，无录入结果{error_suffix}",
                data=data,
            )
        if fallback_from_preview:
            return CrawlerExecutionResultResponseVo(
                code=status.HTTP_200_OK,
                message="获取成功，但当前数据库尚未完成 inserted_article_ids 字段迁移，本次结果基于 result_preview 回退，可能不完整",
                data=data,
            )
        return CrawlerExecutionResultResponseVo(code=status.HTTP_200_OK, message="获取成功", data=data)

    async def list_inserted_data(self, page: int = 1, page_size: int = 20) -> CrawlerInsertedDataListResponseVo:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        total = await self.repo.count_shipping_results()
        total_pages = (total + safe_page_size - 1) // safe_page_size if total > 0 else 0

        if total_pages > 0 and safe_page > total_pages:
            safe_page = total_pages

        records = await self.repo.list_shipping_results(page=safe_page, page_size=safe_page_size)
        return CrawlerInsertedDataListResponseVo(
            code=status.HTTP_200_OK,
            message="获取成功",
            data=records,
            page=safe_page,
            page_size=safe_page_size,
            total=total,
            total_pages=total_pages,
        )