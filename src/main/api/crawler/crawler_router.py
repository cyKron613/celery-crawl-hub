import asyncio
import fastapi
from fastapi import Body, Depends, Path, Query
from lxml import etree

from src.main.core.orm.depend.base import get_async_service
from src.main.repository.crawler_task import CrawlerTaskRepository
from src.main.schema.crawler_task import (
    CrawlerExecutionListResponseVo,
    CrawlerExecutionResultResponseVo,
    CrawlerInsertedDataListResponseVo,
    CrawlerTaskCreateRequest,
    CrawlerTaskDetailResponseVo,
    CrawlerTaskListResponseVo,
    CrawlerTaskRunResponseVo,
    CrawlerTaskScheduleActionResponseVo,
    CrawlerTaskUpdateRequest,
    CrawlerXPathTestRequest,
    CrawlerXPathTestResponseVo,
    CrawlerXPathTestResult,
)
from src.main.service.crawler.crawler_task_service import CrawlerTaskService


router = fastapi.APIRouter(prefix="/v1/crawler", tags=["Crawler Tasks"])


TASK_PAYLOAD_EXAMPLES = {
    "jmd_manual_task": {
        "summary": "手动执行的日本海运新闻采集任务",
        "description": "包含列表页、详情页 XPath、去重与日文来源配置的完整示例。",
        "value": {
            "task_name": "jmd-crawler-demo",
            "description": "日本海运新闻社首页新闻抓取任务",
            "source_name": "jmd",
            "prefix": "https://www.jmd.co.jp",
            "home_url_list": [
                "https://www.jmd.co.jp/"
            ],
            "url_xpath": "//section[@class='kiji-index--category']//h3//a/@href",
            "title_xpath": "//h1[@class='article--title']/text()",
            "content_xpath": "//article[@class='content']//p//text()[not(ancestor::script) and not(ancestor::style)]",
            "home_date_xpath": "//span[@class='text kiji-index--category--kiji_date']//text()",
            "date_xpath": None,
            "image_xpath": None,
            "detail_image_xpath": None,
            "url_limit": 10,
            "list_retry_count": 1,
            "list_retry_sleep_seconds": 3,
            "detail_retry_count": 2,
            "detail_retry_sleep_seconds": 1,
            "min_content_length": 0,
            "max_content_length": 0,
            "dedupe_urls": True,
            "home_wait_xpath": None,
            "detail_wait_xpath": None,
            "source_language": "ja",
            "source_map": {
                "jmd.co.jp": "日本海运新闻社（Japan Marine Daily）"
            },
            "content_joiner": " ",
            "default_image_url": None,
            "date_patterns": [
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
                "%Y-%m-%dT%H:%M:%S.%f%z"
            ],
            "schedule_type": "manual",
            "cron_expression": None,
            "interval_seconds": None,
            "schedule_enabled": False
        },
    },
    "interval_task": {
        "summary": "间隔调度任务",
        "description": "每 30 分钟抓取一次的调度任务示例。",
        "value": {
            "task_name": "jmd-crawler-interval",
            "description": "每 30 分钟自动抓取一次",
            "source_name": "jmd",
            "prefix": "https://www.jmd.co.jp",
            "home_url_list": [
                "https://www.jmd.co.jp/"
            ],
            "url_xpath": "//section[@class='kiji-index--category']//h3//a/@href",
            "title_xpath": "//h1[@class='article--title']/text()",
            "content_xpath": "//article[@class='content']//p//text()[not(ancestor::script) and not(ancestor::style)]",
            "home_date_xpath": "//span[@class='text kiji-index--category--kiji_date']//text()",
            "date_xpath": None,
            "image_xpath": None,
            "detail_image_xpath": None,
            "url_limit": 20,
            "list_retry_count": 2,
            "list_retry_sleep_seconds": 3,
            "detail_retry_count": 2,
            "detail_retry_sleep_seconds": 2,
            "min_content_length": 0,
            "max_content_length": 0,
            "dedupe_urls": True,
            "home_wait_xpath": None,
            "detail_wait_xpath": None,
            "source_language": "ja",
            "source_map": {
                "jmd.co.jp": "日本海运新闻社（Japan Marine Daily）"
            },
            "content_joiner": " ",
            "default_image_url": None,
            "date_patterns": [
                "%Y/%m/%d",
                "%Y-%m-%d"
            ],
            "schedule_type": "interval",
            "cron_expression": None,
            "interval_seconds": 1800,
            "schedule_enabled": True
        },
    },
}


TASK_ID_PATH_EXAMPLES = {
    "task_id": {
        "summary": "任务 ID",
        "value": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    }
}


CELERY_TASK_ID_PATH_EXAMPLES = {
    "celery_task_id": {
        "summary": "Celery 任务 ID",
        "value": "6644ba9b-1720-4211-8dd5-9b4b93b9e776",
    }
}


EXECUTION_LIMIT_QUERY_EXAMPLES = {
    "default_limit": {
        "summary": "最近 20 条",
        "value": 20,
    },
    "debug_limit": {
        "summary": "调试时拉取最近 5 条",
        "value": 5,
    },
}


@router.post(
    path="/tasks",
    summary="创建爬虫任务",
    status_code=fastapi.status.HTTP_201_CREATED,
    response_model=CrawlerTaskDetailResponseVo,
    
)
async def create_crawler_task(
    payload: CrawlerTaskCreateRequest = Body(..., openapi_examples=TASK_PAYLOAD_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskDetailResponseVo:
    return await service.create_task(payload)


@router.post(
    path="/tasks/import",
    summary="导入爬虫任务配置",
    status_code=fastapi.status.HTTP_201_CREATED,
    response_model=CrawlerTaskDetailResponseVo,
)
async def import_crawler_task(
    payload: CrawlerTaskCreateRequest = Body(..., openapi_examples=TASK_PAYLOAD_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskDetailResponseVo:
    return await service.create_task(payload)


@router.get(
    path="/tasks",
    summary="获取爬虫任务列表",
    response_model=CrawlerTaskListResponseVo,
)
async def list_crawler_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskListResponseVo:
    return await service.list_tasks(page=page, page_size=page_size)


@router.get(
    path="/tasks/{task_id}",
    summary="获取爬虫任务详情",
    response_model=CrawlerTaskDetailResponseVo,
)
async def get_crawler_task(
    task_id: str = Path(..., description="任务ID", openapi_examples=TASK_ID_PATH_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskDetailResponseVo:
    return await service.get_task(task_id)


@router.put(
    path="/tasks/{task_id}",
    summary="更新爬虫任务",
    response_model=CrawlerTaskDetailResponseVo,
)
async def update_crawler_task(
    task_id: str = Path(..., description="任务ID", openapi_examples=TASK_ID_PATH_EXAMPLES),
    payload: CrawlerTaskUpdateRequest = Body(..., openapi_examples=TASK_PAYLOAD_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskDetailResponseVo:
    return await service.update_task(task_id, payload)


@router.delete(
    path="/tasks/{task_id}",
    summary="删除爬虫任务",
    response_model=CrawlerTaskScheduleActionResponseVo,
)
async def delete_crawler_task(
    task_id: str = Path(..., description="任务ID", openapi_examples=TASK_ID_PATH_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskScheduleActionResponseVo:
    return await service.delete_task(task_id)


@router.post(
    path="/tasks/{task_id}/run",
    summary="手动执行爬虫任务",
    response_model=CrawlerTaskRunResponseVo,
)
async def run_crawler_task(
    task_id: str = Path(..., description="任务ID", openapi_examples=TASK_ID_PATH_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskRunResponseVo:
    return await service.run_task(task_id)


@router.post(
    path="/tasks/{task_id}/schedule/start",
    summary="开启定时调度",
    response_model=CrawlerTaskScheduleActionResponseVo,
)
async def start_crawler_schedule(
    task_id: str = Path(..., description="任务ID", openapi_examples=TASK_ID_PATH_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskScheduleActionResponseVo:
    return await service.start_schedule(task_id)


@router.post(
    path="/tasks/{task_id}/schedule/pause",
    summary="暂停定时调度",
    response_model=CrawlerTaskScheduleActionResponseVo,
)
async def pause_crawler_schedule(
    task_id: str = Path(..., description="任务ID", openapi_examples=TASK_ID_PATH_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerTaskScheduleActionResponseVo:
    return await service.pause_schedule(task_id)


@router.get(
    path="/tasks/{task_id}/executions",
    summary="获取任务执行记录",
    response_model=CrawlerExecutionListResponseVo,
)
async def list_crawler_executions(
    task_id: str = Path(..., description="任务ID", openapi_examples=TASK_ID_PATH_EXAMPLES),
    limit: int = Query(20, ge=1, le=100, description="返回的执行记录条数", openapi_examples=EXECUTION_LIMIT_QUERY_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerExecutionListResponseVo:
    return await service.list_executions(task_id, limit)


@router.get(
    path="/executions/{celery_task_id}/results",
    summary="根据 celery_task_id 获取正式入库结果",
    response_model=CrawlerExecutionResultResponseVo,
)
async def get_crawler_execution_results(
    celery_task_id: str = Path(..., description="Celery任务ID", openapi_examples=CELERY_TASK_ID_PATH_EXAMPLES),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerExecutionResultResponseVo:
    return await service.get_execution_results(celery_task_id)


@router.get(
    path="/inserted-data",
    summary="分页获取正式入库数据",
    response_model=CrawlerInsertedDataListResponseVo,
)
async def list_crawler_inserted_data(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    service: CrawlerTaskService = Depends(get_async_service(CrawlerTaskService, CrawlerTaskRepository)),
) -> CrawlerInsertedDataListResponseVo:
    return await service.list_inserted_data(page=page, page_size=page_size)


@router.post(
    path="/test-xpath",
    summary="测试 XPath 提取网页内容",
    response_model=CrawlerXPathTestResponseVo,
)
async def test_xpath(
    payload: CrawlerXPathTestRequest = Body(..., description="XPath 测试参数"),
) -> CrawlerXPathTestResponseVo:
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        return CrawlerXPathTestResponseVo(
            code=400,
            message="URL 格式错误，必须以 http:// 或 https:// 开头",
            data=None
        )

    xpaths = [payload.xpath] if isinstance(payload.xpath, str) else list(payload.xpath)
    wait_xpath = None
    if payload.wait_xpath:
        wait_xpath = [payload.wait_xpath] if isinstance(payload.wait_xpath, str) else list(payload.wait_xpath)

    from src.main.config.manager import settings
    engine = settings.CRAWL_ENGINE.lower()

    html = None
    try:
        if engine == "playwright":
            from src.utils.playwright_manager import playwright_fetch
            res = await playwright_fetch(url, timeout=30, wait_xpath=wait_xpath)
            if res and res.get("status"):
                html = res.get("html")
            else:
                err = res.get("error") or "Playwright 获取网页失败"
                return CrawlerXPathTestResponseVo(
                    code=400,
                    message=f"Playwright 抓取失败: {err}",
                    data=None
                )
        else:
            from src.utils.craw_tools import fetch_and_parse
            res = await asyncio.to_thread(
                fetch_and_parse, url, False, 2, 1, 30, wait_xpath
            )
            if res and res.get("status"):
                html = res.get("html")
            else:
                err = res.get("error") or "DrissionPage 获取网页失败"
                return CrawlerXPathTestResponseVo(
                    code=400,
                    message=f"DrissionPage 抓取失败: {err}",
                    data=None
                )
    except Exception as e:
        return CrawlerXPathTestResponseVo(
            code=400,
            message=f"请求目标网页发生异常: {str(e)}",
            data=None
        )

    if not html:
        return CrawlerXPathTestResponseVo(
            code=400,
            message="获取的网页 HTML 源码为空，可能被反爬拦截或超时",
            data=None
        )

    try:
        parsed_html = etree.HTML(html)
    except Exception as e:
        return CrawlerXPathTestResponseVo(
            code=400,
            message=f"解析 HTML 失败: {str(e)}",
            data=None
        )

    extracted = []
    for xpath in xpaths:
        if not xpath.strip():
            continue
        try:
            nodes = parsed_html.xpath(xpath)
            if not nodes:
                continue
            for node in nodes:
                if isinstance(node, str):
                    cleaned = node.strip()
                    if cleaned:
                        extracted.append(cleaned)
                elif hasattr(node, "xpath"):
                    txt = "".join(node.xpath(".//text()")).replace("\xa0", " ").strip()
                    if txt:
                        extracted.append(txt)
                else:
                    cleaned = str(node).strip()
                    if cleaned:
                        extracted.append(cleaned)
        except Exception as e:
            return CrawlerXPathTestResponseVo(
                code=400,
                message=f"XPath 语法错误 '{xpath}': {str(e)}",
                data=None
            )

    if not extracted:
        return CrawlerXPathTestResponseVo(
            code=400,
            message="❌ XPath 未提取到任何内容。请检查 XPath 语法规则是否匹配当前网页结构！",
            data=None
        )

    return CrawlerXPathTestResponseVo(
        code=200,
        message="提取成功",
        data=CrawlerXPathTestResult(extracted=extracted)
    )