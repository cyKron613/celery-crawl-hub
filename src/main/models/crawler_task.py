from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from src.main.config.manager import settings
from src.main.core.orm.model.base import BaseModel as Base, generate_uuid


POSTGRES_SCHEMA = settings.POSTGRES_SCHEMA


class CrawlerTask(Base):
    __tablename__ = "crawler_tasks"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    id = Column(UUID, primary_key=True, default=generate_uuid, comment="主键ID")
    task_name = Column(String(100), nullable=False, unique=True, comment="任务名称")
    description = Column(Text, nullable=True, comment="任务描述")
    source_name = Column(String(100), nullable=False, comment="来源名称")
    prefix = Column(String(500), nullable=True, comment="URL前缀")
    home_url_list = Column(JSONB, nullable=False, comment="首页URL列表")
    url_xpath = Column(JSONB, nullable=False, comment="列表详情链接XPath")
    title_xpath = Column(JSONB, nullable=False, comment="详情标题XPath")
    content_xpath = Column(JSONB, nullable=False, comment="详情正文XPath")
    home_date_xpath = Column(JSONB, nullable=True, comment="列表日期XPath")
    date_xpath = Column(JSONB, nullable=True, comment="详情日期XPath")
    image_xpath = Column(JSONB, nullable=True, comment="列表图片XPath")
    detail_image_xpath = Column(JSONB, nullable=True, comment="详情图片XPath")
    url_limit = Column(Integer, nullable=False, default=10, comment="单次抓取上限")
    list_retry_count = Column(Integer, nullable=False, default=1, comment="列表页重试次数")
    list_retry_sleep_seconds = Column(Integer, nullable=False, default=3, comment="列表页重试间隔")
    detail_retry_count = Column(Integer, nullable=False, default=0, comment="详情页重试次数")
    detail_retry_sleep_seconds = Column(Integer, nullable=False, default=2, comment="详情页重试间隔")
    min_content_length = Column(Integer, nullable=False, default=0, comment="正文最小长度")
    max_content_length = Column(Integer, nullable=False, default=0, comment="正文最大长度")
    dedupe_urls = Column(Boolean, nullable=False, default=False, comment="是否去重URL")
    home_wait_xpath = Column(JSONB, nullable=True, comment="首页等待XPath")
    detail_wait_xpath = Column(JSONB, nullable=True, comment="详情页等待XPath")
    source_language = Column(String(20), nullable=False, default="auto", comment="来源语言")
    source_map = Column(JSONB, nullable=True, comment="来源映射")
    content_joiner = Column(String(20), nullable=False, default=" ", comment="内容拼接符")
    default_image_url = Column(Text, nullable=True, comment="默认图片")
    date_patterns = Column(JSONB, nullable=True, comment="日期格式列表")
    schedule_type = Column(String(20), nullable=False, default="manual", comment="调度类型")
    cron_expression = Column(String(120), nullable=True, comment="Cron表达式")
    interval_seconds = Column(Integer, nullable=True, comment="间隔秒数")
    schedule_enabled = Column(Boolean, nullable=False, default=False, comment="是否启用调度")
    next_run_at = Column(TIMESTAMP(timezone=True), nullable=True, comment="下次执行时间")
    last_run_at = Column(TIMESTAMP(timezone=True), nullable=True, comment="最近执行时间")
    last_status = Column(String(20), nullable=False, default="idle", comment="最近执行状态")
    last_error = Column(Text, nullable=True, comment="最近错误信息")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="更新时间",
    )


class CrawlerTaskExecution(Base):
    __tablename__ = "crawler_task_executions"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    id = Column(UUID, primary_key=True, default=generate_uuid, comment="主键ID")
    task_id = Column(UUID, ForeignKey(f"{POSTGRES_SCHEMA}.crawler_tasks.id", ondelete="CASCADE"), nullable=False, comment="任务ID")
    trigger_type = Column(String(20), nullable=False, comment="触发类型")
    status = Column(String(20), nullable=False, comment="执行状态")
    celery_task_id = Column(String(100), nullable=True, comment="Celery任务ID")
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment="开始时间")
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True, comment="结束时间")
    result_count = Column(Integer, nullable=False, default=0, comment="结果数量")
    error_message = Column(Text, nullable=True, comment="错误信息")
    result_preview = Column(JSONB, nullable=True, comment="结果预览")
    inserted_article_ids = Column(JSONB, nullable=True, comment="已入库 article_id 列表")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment="创建时间")