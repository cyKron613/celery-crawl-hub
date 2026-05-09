from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


XPathInput = str | list[str] | None


def _normalize_xpath_value(value: XPathInput) -> XPathInput:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    normalized = [item.strip() for item in value if item and item.strip()]
    return normalized or None


class CrawlerTaskBaseRequest(BaseModel):
    task_name: str = Field(..., description="任务名称")
    description: str | None = Field(None, description="任务描述")
    source_name: str = Field(..., description="来源名称")
    prefix: str | None = Field(None, description="URL前缀")
    home_url_list: list[str] = Field(..., min_length=1, description="首页URL列表")
    url_xpath: XPathInput = Field(..., description="列表详情链接XPath")
    title_xpath: XPathInput = Field(..., description="详情标题XPath")
    content_xpath: XPathInput = Field(..., description="详情正文XPath")
    home_date_xpath: XPathInput = Field(None, description="列表日期XPath")
    date_xpath: XPathInput = Field(None, description="详情日期XPath")
    image_xpath: XPathInput = Field(None, description="列表图片XPath")
    detail_image_xpath: XPathInput = Field(None, description="详情图片XPath")
    url_limit: int = Field(10, ge=1, le=200, description="单次抓取详情页数量")
    list_retry_count: int = Field(1, ge=0, le=10, description="列表页重试次数")
    list_retry_sleep_seconds: int = Field(3, ge=0, le=60, description="列表页重试间隔")
    detail_retry_count: int = Field(0, ge=0, le=10, description="详情页重试次数")
    detail_retry_sleep_seconds: int = Field(2, ge=0, le=60, description="详情页重试间隔")
    min_content_length: int = Field(..., description="正文最小长度")
    max_content_length: int = Field(..., description="正文最大长度")
    dedupe_urls: bool = Field(False, description="是否去重URL")
    home_wait_xpath: XPathInput = Field(None, description="首页等待XPath")
    detail_wait_xpath: XPathInput = Field(None, description="详情页等待XPath")
    source_language: str = Field("auto", description="来源语言")
    source_map: dict[str, str] = Field(default_factory=dict, description="域名与来源名映射")
    content_joiner: str = Field(" ", description="正文拼接符")
    default_image_url: str | None = Field(None, description="默认图片URL")
    date_patterns: list[str] = Field(
        default_factory=lambda: [
            "%d/%m/%y",
            "%d %B %Y",
            "%d %b %Y",
            "%B %d, %Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ],
        description="日期格式列表",
    )
    schedule_type: str = Field("manual", description="调度类型：manual/interval/cron")
    cron_expression: str | None = Field(None, description="Cron表达式")
    interval_seconds: int | None = Field(None, ge=1, description="间隔秒数")
    schedule_enabled: bool = Field(False, description="是否启用调度")

    @field_validator("task_name", "source_name", mode="before")
    @classmethod
    def validate_required_text(cls, value: Any) -> str:
        if value is None or not str(value).strip():
            raise ValueError("字段不能为空")
        return str(value).strip()

    @field_validator("prefix", "description", "default_image_url", "cron_expression", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("home_url_list", mode="before")
    @classmethod
    def validate_home_url_list(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("home_url_list 至少包含一个URL")
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if not normalized:
            raise ValueError("home_url_list 至少包含一个有效URL")
        return normalized

    @field_validator(
        "url_xpath",
        "title_xpath",
        "content_xpath",
        "home_date_xpath",
        "date_xpath",
        "image_xpath",
        "detail_image_xpath",
        "home_wait_xpath",
        "detail_wait_xpath",
        mode="before",
    )
    @classmethod
    def normalize_xpath_fields(cls, value: Any) -> XPathInput:
        return _normalize_xpath_value(value)

    @field_validator("schedule_type", mode="before")
    @classmethod
    def normalize_schedule_type(cls, value: Any) -> str:
        normalized = str(value or "manual").strip().lower()
        if normalized not in {"manual", "interval", "cron"}:
            raise ValueError("schedule_type 仅支持 manual、interval、cron")
        return normalized

    @field_validator("date_patterns", mode="before")
    @classmethod
    def normalize_date_patterns(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("date_patterns 必须是字符串数组")
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.max_content_length > 0 and self.max_content_length < self.min_content_length:
            raise ValueError("max_content_length 不能小于 min_content_length")
        if self.schedule_type == "interval" and not self.interval_seconds:
            raise ValueError("interval 调度必须提供 interval_seconds")
        if self.schedule_type == "cron" and not self.cron_expression:
            raise ValueError("cron 调度必须提供 cron_expression")
        if self.schedule_type == "manual":
            self.cron_expression = None
            self.interval_seconds = None
            if self.schedule_enabled:
                raise ValueError("manual 调度不能启用 schedule_enabled")
        return self


class CrawlerTaskCreateRequest(CrawlerTaskBaseRequest):
    pass


class CrawlerTaskUpdateRequest(CrawlerTaskBaseRequest):
    pass


class CrawlerTaskResponse(BaseModel):
    id: UUID = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    description: str | None = Field(None, description="任务描述")
    source_name: str = Field(..., description="来源名称")
    prefix: str | None = Field(None, description="URL前缀")
    home_url_list: list[str] = Field(..., description="首页URL列表")
    url_xpath: XPathInput = Field(..., description="列表详情链接XPath")
    title_xpath: XPathInput = Field(..., description="详情标题XPath")
    content_xpath: XPathInput = Field(..., description="详情正文XPath")
    home_date_xpath: XPathInput = Field(None, description="列表日期XPath")
    date_xpath: XPathInput = Field(None, description="详情日期XPath")
    image_xpath: XPathInput = Field(None, description="列表图片XPath")
    detail_image_xpath: XPathInput = Field(None, description="详情图片XPath")
    url_limit: int = Field(..., description="单次抓取上限")
    list_retry_count: int = Field(..., description="列表页重试次数")
    list_retry_sleep_seconds: int = Field(..., description="列表页重试间隔")
    detail_retry_count: int = Field(..., description="详情页重试次数")
    detail_retry_sleep_seconds: int = Field(..., description="详情页重试间隔")
    min_content_length: int = Field(..., description="正文最小长度")
    max_content_length: int = Field(..., description="正文最大长度")
    dedupe_urls: bool = Field(..., description="是否去重")
    home_wait_xpath: XPathInput = Field(None, description="首页等待XPath")
    detail_wait_xpath: XPathInput = Field(None, description="详情页等待XPath")
    source_language: str = Field(..., description="来源语言")
    source_map: dict[str, str] = Field(default_factory=dict, description="域名来源映射")
    content_joiner: str = Field(..., description="正文拼接符")
    default_image_url: str | None = Field(None, description="默认图片")
    date_patterns: list[str] = Field(default_factory=list, description="日期格式列表")
    schedule_type: str = Field(..., description="调度类型")
    cron_expression: str | None = Field(None, description="Cron表达式")
    interval_seconds: int | None = Field(None, description="间隔秒数")
    schedule_enabled: bool = Field(..., description="是否启用调度")
    next_run_at: datetime | None = Field(None, description="下次执行时间")
    last_run_at: datetime | None = Field(None, description="上次执行时间")
    last_status: str = Field(..., description="最近执行状态")
    last_error: str | None = Field(None, description="最近错误")
    created_at: datetime | None = Field(None, description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class CrawlerTaskExecutionResponse(BaseModel):
    id: UUID = Field(..., description="执行记录ID")
    task_id: UUID = Field(..., description="任务ID")
    trigger_type: str = Field(..., description="触发类型")
    status: str = Field(..., description="执行状态")
    celery_task_id: str | None = Field(None, description="Celery任务ID")
    started_at: datetime | None = Field(None, description="开始时间")
    finished_at: datetime | None = Field(None, description="结束时间")
    result_count: int = Field(..., description="结果数量")
    error_message: str | None = Field(None, description="错误信息")
    result_preview: list[dict[str, Any]] | None = Field(None, description="结果预览")
    inserted_article_ids: list[str] | None = Field(None, description="已入库 article_id 列表")

    model_config = ConfigDict(from_attributes=True)


class ShippingInformationResponse(BaseModel):
    uuid: str | None = Field(None, description="UUID")
    img_parse_url: str | None = Field(None, description="图片解析地址")
    detail_url: str | None = Field(None, description="详情页地址")
    detail_title: str | None = Field(None, description="标题")
    detail_date: date | None = Field(None, description="详情日期")
    detail_timestamptz: str | None = Field(None, description="带时区时间")
    detail_contents: str | None = Field(None, description="正文")
    article_id: str = Field(..., description="文章主键")
    update_time: datetime | None = Field(None, description="更新时间")
    class_level_1: str | None = Field(None, description="一级分类")
    class_level_2: str | None = Field(None, description="二级分类")
    news_source_name_cn: str | None = Field(None, description="中文来源名称")
    keyword1: str | None = Field(None, description="关键词1")
    keyword2: str | None = Field(None, description="关键词2")
    keyword3: str | None = Field(None, description="关键词3")
    is_translated: str | None = Field(None, description="是否翻译")
    abstract: str | None = Field(None, description="摘要")
    detail_title_cn: str | None = Field(None, description="中文标题")
    detail_contents_cn: str | None = Field(None, description="中文正文")
    abstract_cn: str | None = Field(None, description="中文摘要")
    obs_url: str | None = Field(None, description="OBS 地址")

    model_config = ConfigDict(from_attributes=True)


class CrawlerExecutionResultData(BaseModel):
    execution_id: UUID | None = Field(None, description="执行记录ID")
    task_id: UUID | None = Field(None, description="任务ID")
    celery_task_id: str = Field(..., description="Celery任务ID")
    status: str | None = Field(None, description="执行状态")
    error_message: str | None = Field(None, description="执行异常信息")
    started_at: datetime | None = Field(None, description="开始时间")
    finished_at: datetime | None = Field(None, description="结束时间")
    result_count: int = Field(0, description="结果数量")
    inserted_article_ids: list[str] = Field(default_factory=list, description="已入库 article_id 列表")
    records: list[ShippingInformationResponse] = Field(default_factory=list, description="正式入库结果")


class CrawlerTaskDetailResponseVo(BaseModel):
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: CrawlerTaskResponse | None = Field(None, description="任务详情")


class CrawlerTaskListResponseVo(BaseModel):
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: list[CrawlerTaskResponse] = Field(default_factory=list, description="任务列表")
    page: int = Field(1, ge=1, description="当前页")
    page_size: int = Field(20, ge=1, description="每页条数")
    total: int = Field(0, ge=0, description="总任务数")
    total_pages: int = Field(0, ge=0, description="总页数")


class CrawlerInsertedDataListResponseVo(BaseModel):
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: list[ShippingInformationResponse] = Field(default_factory=list, description="正式入库数据列表")
    page: int = Field(1, ge=1, description="当前页")
    page_size: int = Field(20, ge=1, description="每页条数")
    total: int = Field(0, ge=0, description="总数据量")
    total_pages: int = Field(0, ge=0, description="总页数")


class CrawlerTaskRunResponseVo(BaseModel):
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: dict[str, str] | None = Field(None, description="执行任务信息")


class CrawlerTaskScheduleActionResponseVo(BaseModel):
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: dict[str, str | bool | None] | None = Field(None, description="调度状态")


class CrawlerExecutionListResponseVo(BaseModel):
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: list[CrawlerTaskExecutionResponse] = Field(default_factory=list, description="执行记录")


class CrawlerExecutionResultResponseVo(BaseModel):
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: CrawlerExecutionResultData | None = Field(None, description="执行结果")