import asyncio
import datetime as dt
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from croniter import croniter
from celery.signals import task_failure  # type: ignore[import-not-found]
from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.main.config.manager import settings
from src.main.crawler.runtime import ConfigurableXPathCrawler
from src.main.models.crawler_result import ExShippingInformation
from src.main.models.crawler_task import CrawlerTask, CrawlerTaskExecution
from src.main.tasks.celery_app import celery_app
from src.utils.ai_tools import match_web_url_class_label_2
from src.utils.source_name_mapping import map_source_name_cn_by_url


SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_preview(records: list[dict]) -> list[dict]:
    return records[: settings.CRAWLER_EXECUTION_PREVIEW_LIMIT]


def _get_base_url(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _resolve_log_base_url(task: CrawlerTask, records: list[dict] | None = None) -> str:
    if records:
        for record in records:
            base_url = _get_base_url(record.get("detail_url") or "")
            if base_url:
                return base_url
    for home_url in task.home_url_list or []:
        base_url = _get_base_url(home_url)
        if base_url:
            return base_url
    return ""


def _resolve_log_table_reference() -> tuple[str, str] | None:
    raw_table_name = (settings.CRAWLER_LOG_TABLE_NAME or "").strip()
    if not raw_table_name:
        return None

    parts = raw_table_name.split(".")
    if len(parts) == 1:
        schema_name, table_name = settings.POSTGRES_SCHEMA, parts[0]
    elif len(parts) == 2:
        schema_name, table_name = parts
    else:
        logger.warning(f"非法日志表配置，已跳过日志写入: {raw_table_name}")
        return None

    if not SQL_IDENTIFIER_RE.fullmatch(schema_name) or not SQL_IDENTIFIER_RE.fullmatch(table_name):
        logger.warning(f"非法日志表配置，已跳过日志写入: {raw_table_name}")
        return None
    return schema_name, table_name


def _ensure_row_uuid(record: dict) -> None:
    current_uuid = record.get("uuid")
    normalized_uuid = str(current_uuid or "").strip()
    if not normalized_uuid or normalized_uuid.lower() == "uuid()":
        record["uuid"] = str(uuid.uuid4())


def _enrich_shipping_records(records: list[dict]) -> list[dict]:
    enriched_records: list[dict] = []
    for record in records:
        enriched_record = dict(record)
        _ensure_row_uuid(enriched_record)

        detail_title = enriched_record.get("detail_title") or enriched_record.get("detail_title_cn") or ""
        detail_contents = enriched_record.get("detail_contents") or enriched_record.get("detail_contents_cn") or ""
        detail_url = enriched_record.get("detail_url") or ""
        class_level_1 = enriched_record.get("class_level_1") or ""

        enriched_record["news_source_name_cn"] = enriched_record.get("news_source_name_cn") or map_source_name_cn_by_url(detail_url)
        enriched_record["class_level_2"] = match_web_url_class_label_2(
            detail_title,
            detail_contents,
            detail_url,
            class_level_1,
        )
        enriched_records.append(enriched_record)
    return enriched_records


async def _write_crawl_log(
    session_factory: async_sessionmaker[AsyncSession],
    website_name: str,
    base_url: str,
    crawl_log: str,
) -> None:
    table_reference = _resolve_log_table_reference()
    if table_reference is None:
        return

    schema_name, table_name = table_reference
    async with session_factory() as session:
        try:
            exists_stmt = text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema_name
                  AND table_name = :table_name
                LIMIT 1
                """
            )
            exists_result = await session.execute(exists_stmt, {"schema_name": schema_name, "table_name": table_name})
            if exists_result.scalar_one_or_none() is None:
                logger.warning(f"日志表不存在，已跳过日志写入: {schema_name}.{table_name}")
                return

            await session.execute(
                text(
                    f"INSERT INTO {schema_name}.{table_name} (website_name, base_url, crawl_log) "
                    "VALUES (:website_name, :base_url, :crawl_log)"
                ),
                {
                    "website_name": website_name,
                    "base_url": base_url,
                    "crawl_log": crawl_log,
                },
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.warning(f"写入日志表失败，已跳过，不影响主流程: {exc}")


async def _has_execution_inserted_article_ids_column(session: AsyncSession) -> bool:
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
    result = await session.execute(stmt, {"schema_name": settings.POSTGRES_SCHEMA})
    return result.scalar_one_or_none() is not None


async def _get_shipping_table_columns(session: AsyncSession) -> set[str]:
    stmt = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema_name
          AND table_name = 'ex_shipping_information'
        """
    )
    result = await session.execute(stmt, {"schema_name": settings.POSTGRES_SCHEMA})
    return {row[0] for row in result.fetchall()}


def _normalize_shipping_record(record: dict) -> dict:
    normalized = {
        "uuid": record.get("uuid"),
        "img_parse_url": record.get("img_parse_url"),
        "detail_url": record.get("detail_url"),
        "detail_title": record.get("detail_title"),
        "detail_date": record.get("detail_date"),
        "detail_timestamptz": record.get("detail_timestamptz"),
        "detail_contents": record.get("detail_contents"),
        "article_id": record.get("article_id"),
        "class_level_1": record.get("class_level_1"),
        "class_level_2": record.get("class_level_2"),
        "news_source_name_cn": record.get("news_source_name_cn"),
        "keyword1": record.get("keyword1"),
        "keyword2": record.get("keyword2"),
        "keyword3": record.get("keyword3"),
        "is_translated": record.get("is_translated") or "no",
        "abstract": record.get("abstract"),
        "detail_title_cn": record.get("detail_title_cn"),
        "detail_contents_cn": record.get("detail_contents_cn"),
        "abstract_cn": record.get("abstract_cn"),
        "obs_url": record.get("obs_url"),
    }
    detail_date = normalized.get("detail_date")
    if isinstance(detail_date, str) and detail_date:
        normalized["detail_date"] = dt.date.fromisoformat(detail_date)
    return normalized


def _dedupe_shipping_records(records: list[dict]) -> list[dict]:
    deduped_records: dict[str, dict] = {}
    for record in records:
        article_id = record.get("article_id")
        if not article_id:
            continue
        deduped_records[article_id] = _normalize_shipping_record(record)
    return list(deduped_records.values())


async def _persist_shipping_records(session: AsyncSession, records: list[dict]) -> list[str]:
    normalized_records = _dedupe_shipping_records(records)
    if not normalized_records:
        return []

    prepared_records = _enrich_shipping_records(normalized_records)

    existing_columns = await _get_shipping_table_columns(session)
    if not existing_columns:
        raise ValueError("ex_shipping_information 表不存在或无法读取列信息")

    filtered_records = []
    for record in prepared_records:
        filtered_record = {key: value for key, value in record.items() if key in existing_columns}
        if filtered_record.get("article_id"):
            filtered_records.append(filtered_record)

    if not filtered_records:
        return []

    stmt = (
        pg_insert(ExShippingInformation)
        .values(filtered_records)
        .on_conflict_do_nothing(index_elements=[ExShippingInformation.article_id])
        .returning(ExShippingInformation.article_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _build_async_db_uri() -> str:
    return (
        f"{settings.POSTGRES_CONNECT}://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    ).replace("postgresql://", "postgresql+asyncpg://")


def _create_session_factory() -> Tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(
        _build_async_db_uri(),
        echo=settings.IS_DB_ECHO_LOG,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "application_name": "crawler-studio-celery",
            }
        },
    )
    return async_sessionmaker(bind=engine, expire_on_commit=False), engine


def _compute_next_run_at(task: CrawlerTask, anchor: datetime | None = None) -> datetime | None:
    now = anchor or _utcnow()
    if task.schedule_type == "manual":
        return None
    if task.schedule_type == "interval":
        return now + timedelta(seconds=task.interval_seconds or 0)
    if not task.cron_expression or not croniter.is_valid(task.cron_expression):
        raise ValueError("无效的 cron_expression")
    local_tz = ZoneInfo(settings.CELERY_TIMEZONE)
    local_now = now.astimezone(local_tz)
    next_local_run = croniter(task.cron_expression, local_now).get_next(datetime)
    if next_local_run.tzinfo is None:
        next_local_run = next_local_run.replace(tzinfo=local_tz)
    return next_local_run.astimezone(timezone.utc)


def _task_to_runtime_config(task: CrawlerTask) -> dict:
    return {
        "source_name": task.source_name,
        "prefix": task.prefix,
        "home_url_list": task.home_url_list,
        "url_xpath": task.url_xpath,
        "title_xpath": task.title_xpath,
        "content_xpath": task.content_xpath,
        "home_date_xpath": task.home_date_xpath,
        "date_xpath": task.date_xpath,
        "image_xpath": task.image_xpath,
        "detail_image_xpath": task.detail_image_xpath,
        "url_limit": task.url_limit,
        "list_retry_count": task.list_retry_count,
        "list_retry_sleep_seconds": task.list_retry_sleep_seconds,
        "detail_retry_count": task.detail_retry_count,
        "detail_retry_sleep_seconds": task.detail_retry_sleep_seconds,
        "min_content_length": task.min_content_length,
        "max_content_length": task.max_content_length,
        "dedupe_urls": task.dedupe_urls,
        "home_wait_xpath": task.home_wait_xpath,
        "detail_wait_xpath": task.detail_wait_xpath,
        "source_language": task.source_language,
        "source_map": task.source_map,
        "content_joiner": task.content_joiner,
        "default_image_url": task.default_image_url,
        "date_patterns": task.date_patterns,
    }


async def _execute_crawler_task(task_id: str, trigger_type: str, celery_task_id: str | None) -> dict:
    session_factory, engine = _create_session_factory()
    try:
        async with session_factory() as session:
            task = await session.get(CrawlerTask, task_id)
            if not task:
                raise ValueError("任务不存在")

            execution = None
            if celery_task_id:
                execution_result = await session.execute(
                    select(CrawlerTaskExecution)
                    .where(CrawlerTaskExecution.celery_task_id == celery_task_id)
                    .order_by(CrawlerTaskExecution.created_at.desc())
                    .limit(1)
                )
                execution = execution_result.scalar_one_or_none()

            if execution is None:
                execution = CrawlerTaskExecution(
                    task_id=task_id,
                    trigger_type=trigger_type,
                    status="running",
                    celery_task_id=celery_task_id,
                )
                session.add(execution)

            execution.task_id = task_id
            execution.trigger_type = trigger_type
            execution.status = "running"
            execution.started_at = _utcnow()
            has_inserted_article_ids_column = await _has_execution_inserted_article_ids_column(session)
            session.add(execution)
            await session.commit()

            try:
                crawler = ConfigurableXPathCrawler(_task_to_runtime_config(task))
                records = await asyncio.to_thread(crawler.run)
                inserted_article_ids = await _persist_shipping_records(session, records)
                execution.status = "success"
                execution.finished_at = _utcnow()
                execution.result_count = len(inserted_article_ids)
                execution.result_preview = _build_preview(records)
                if has_inserted_article_ids_column:
                    execution.inserted_article_ids = inserted_article_ids
                task.last_run_at = _utcnow()
                task.last_status = "success"
                task.last_error = None
                session.add_all([execution, task])
                await session.commit()
                execution_id = execution.id
                result_count = len(inserted_article_ids)
                await _write_crawl_log(
                    session_factory,
                    website_name=task.source_name,
                    base_url=_resolve_log_base_url(task, records),
                    crawl_log=(
                        "无新数据插入"
                        if not inserted_article_ids
                        else f"成功同步 {len(inserted_article_ids)} 条数据"
                    ),
                )
                return {"execution_id": execution_id, "result_count": result_count}
            except Exception as exc:
                await session.rollback()
                execution.status = "failed"
                execution.finished_at = _utcnow()
                execution.error_message = str(exc)
                task.last_run_at = _utcnow()
                task.last_status = "failed"
                task.last_error = str(exc)
                session.add_all([execution, task])
                await session.commit()
                await _write_crawl_log(
                    session_factory,
                    website_name=task.source_name,
                    base_url=_resolve_log_base_url(task),
                    crawl_log=f"任务执行失败: {exc}",
                )
                logger.exception("爬虫任务执行失败")
                raise
    finally:
        await engine.dispose()


async def _mark_task_failed_after_outer_exception(
    task_id: str,
    trigger_type: str,
    celery_task_id: str | None,
    error_message: str,
) -> None:
    """兜底写入失败状态，覆盖硬超时等外层异常未落库的场景。"""
    session_factory, engine = _create_session_factory()
    try:
        async with session_factory() as session:
            task = await session.get(CrawlerTask, task_id)
            if not task:
                return

            execution = None
            if celery_task_id:
                execution_result = await session.execute(
                    select(CrawlerTaskExecution)
                    .where(CrawlerTaskExecution.celery_task_id == celery_task_id)
                    .order_by(CrawlerTaskExecution.created_at.desc())
                    .limit(1)
                )
                execution = execution_result.scalar_one_or_none()

            if execution is None:
                execution = CrawlerTaskExecution(
                    task_id=task_id,
                    trigger_type=trigger_type,
                    status="failed",
                    celery_task_id=celery_task_id,
                    started_at=_utcnow(),
                )

            if execution.status != "success":
                execution.task_id = task_id
                execution.trigger_type = trigger_type
                execution.status = "failed"
                execution.finished_at = _utcnow()
                execution.error_message = error_message

            task.last_run_at = _utcnow()
            task.last_status = "failed"
            task.last_error = error_message

            session.add_all([execution, task])
            await session.commit()

            await _write_crawl_log(
                session_factory,
                website_name=task.source_name,
                base_url=_resolve_log_base_url(task),
                crawl_log=f"任务执行失败(外层异常): {error_message}",
            )
    finally:
        await engine.dispose()


async def _dispatch_due_tasks() -> int:
    session_factory, engine = _create_session_factory()
    try:
        async with session_factory() as session:
            from sqlalchemy import select

            now = _utcnow()
            result = await session.execute(
                select(CrawlerTask)
                .where(CrawlerTask.schedule_enabled.is_(True))
                .where(CrawlerTask.next_run_at.is_not(None))
                .where(CrawlerTask.next_run_at <= now)
            )
            due_tasks = list(result.scalars().all())

            dispatched = 0
            for task in due_tasks:
                task.next_run_at = _compute_next_run_at(task, anchor=now)
                session.add(task)
                dispatched += 1
            await session.commit()

            if due_tasks:
                for task in due_tasks:
                    execute_crawler_task.delay(task_id=task.id, trigger_type="schedule")
            return dispatched
    finally:
        await engine.dispose()


@celery_app.task(name="crawler.execute_task", bind=True)
def execute_crawler_task(self, task_id: str, trigger_type: str = "manual"):
    try:
        return asyncio.run(_execute_crawler_task(task_id=task_id, trigger_type=trigger_type, celery_task_id=self.request.id))
    except BaseException as exc:
        outer_error = f"{type(exc).__name__}: {exc}"
        try:
            asyncio.run(
                _mark_task_failed_after_outer_exception(
                    task_id=task_id,
                    trigger_type=trigger_type,
                    celery_task_id=self.request.id,
                    error_message=outer_error,
                )
            )
        except Exception:
            logger.exception("外层异常兜底落库失败")
        raise


def _extract_execute_task_payload(args: tuple | None, kwargs: dict | None) -> tuple[str | None, str]:
    task_id = None
    trigger_type = "manual"

    if kwargs:
        task_id = kwargs.get("task_id")
        trigger_type = kwargs.get("trigger_type", trigger_type)

    if task_id is None and args:
        if len(args) >= 1:
            task_id = args[0]
        if len(args) >= 2 and args[1]:
            trigger_type = args[1]

    return task_id, trigger_type


@task_failure.connect
def on_execute_task_failure(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    **extra,
):
    sender_name = getattr(sender, "name", None)
    if sender_name != "crawler.execute_task":
        return

    # 硬超时会终止子进程，任务内 try/except 无法执行；仅在此类异常时做主进程兜底落库。
    exception_name = type(exception).__name__ if exception else ""
    if exception_name not in {"TimeLimitExceeded", "WorkerLostError"}:
        return

    inner_task_id, trigger_type = _extract_execute_task_payload(args=args, kwargs=kwargs)
    if not inner_task_id:
        logger.warning(f"任务失败信号缺少业务 task_id，无法兜底落库。celery_task_id={task_id}")
        return

    error_message = f"{exception_name}: {exception}"
    try:
        asyncio.run(
            _mark_task_failed_after_outer_exception(
                task_id=inner_task_id,
                trigger_type=trigger_type,
                celery_task_id=task_id,
                error_message=error_message,
            )
        )
    except Exception:
        logger.exception("任务失败信号兜底落库失败")


@celery_app.task(name="crawler.dispatch_due_tasks")
def dispatch_due_tasks() -> int:
    return asyncio.run(_dispatch_due_tasks())