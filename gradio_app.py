import json
import os
from html import escape
from typing import Any, Dict, List, Tuple

import gradio as gr
import requests
from dotenv import load_dotenv


load_dotenv()


API_BASE_URL = os.getenv("GRADIO_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
SERVER_HOST = os.getenv("GRADIO_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
APP_TITLE = os.getenv("GRADIO_APP_TITLE", "Crawler Studio Console")


DEFAULT_TASK_TEMPLATE = {
    "task_name": "jmd-crawler",
    "description": "日本海运新闻社首页新闻抓取任务",
    "source_name": "jmd",
    "prefix": "https://www.jmd.co.jp",
    "home_url_list": ["https://www.jmd.co.jp/"],
    "url_xpath": "//section[@class=\"kiji-index--category\"]//h3//a/@href",
    "title_xpath": "//h1[@class=\"article--title\"]/text()",
    "content_xpath": "//article[@class=\"content\"]//p//text()[not(ancestor::script) and not(ancestor::style)]",
    "home_date_xpath": "//span[@class=\"text kiji-index--category--kiji_date\"]//text()",
    "date_xpath": None,
    "image_xpath": None,
    "detail_image_xpath": None,
    "url_limit": 10,
    "list_retry_count": 1,
    "list_retry_sleep_seconds": 3,
    "detail_retry_count": 2,
    "detail_retry_sleep_seconds": 1,
    "home_request_delay_seconds": 0,
    "home_request_delay_jitter_seconds": 0,
    "detail_request_delay_seconds": 0,
    "detail_request_delay_jitter_seconds": 0,
    "fetch_timeout": 360,
    "login_enabled": False,
    "login_username": "",
    "login_password": "",
    "playwright_login_url": "",
    "playwright_login_entry_xpath": "",
    "playwright_login_username_xpath": "",
    "playwright_login_password_xpath": "",
    "playwright_login_submit_xpath": "",
    "playwright_login_success_xpath": "",
    "playwright_login_timeout": 60,
    "playwright_headless": True,
    "enable_content_image_placeholder": False,
    "content_root_xpath": None,
    "content_image_xpath": ".//img/@src",
    "content_image_placeholder_template": "![图片{index}]({url})",
    "append_content_image_mapping": False,
    "category": "",
    "min_content_length": 0,
    "max_content_length": 0,
    "dedupe_urls": True,
    "home_wait_xpath": None,
    "detail_wait_xpath": None,
    "source_language": "ja",
    "source_map": {"jmd.co.jp": "日本海运新闻社（Japan Marine Daily）"},
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
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y年%m月%d日"
    ],
    "schedule_type": "manual",
    "cron_expression": None,
    "interval_seconds": None,
    "schedule_enabled": False,
}


THEME_CSS = """
:root {
    --bg: #f6f8fa;
    --panel: #ffffff;
    --panel-soft: #f6f8fa;
    --soft-yellow: #fff8cc;
    --ink: #000000;
    --muted: #000000;
    --line: #d0d7de;
    --accent: #0969da;
    --accent-hover: #0550ae;
    --danger: #cf222e;
    --danger-hover: #a40e26;
}

html,
body {
    margin: 0 !important;
    min-height: 100vh;
    background: var(--bg) !important;
}

body,
.gradio-container,
.gradio-container .main {
    background: var(--bg) !important;
    color: var(--ink) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif !important;
}

.gradio-container {
    width: min(1180px, calc(100vw - 48px)) !important;
    max-width: 1180px !important;
    margin: 0 auto !important;
    padding-bottom: 24px !important;
}

.app-shell {
    padding: 0;
    border-radius: 0;
    background: transparent;
    border: none;
    box-shadow: none;
}

.gradio-container .main {
    padding-top: 24px;
}

.gradio-container * {
    color: var(--ink) !important;
}

.hero-card,
.block,
.gr-box,
.gr-form,
.gr-panel,
.gr-group {
    background: var(--panel) !important;
  border: 1px solid var(--line);
    border-radius: 6px !important;
    box-shadow: none !important;
}

.hero-card {
    padding: 24px;
}

.hero-title {
    margin: 0 0 8px 0;
    font-size: 32px;
    line-height: 1.25;
    font-weight: 600;
    color: var(--ink);
}

.hero-subtitle {
  margin: 0;
    font-size: 14px;
    color: var(--muted);
    opacity: 1;
}

.section-note {
  margin-top: 16px;
  padding: 12px 14px;
    border-radius: 6px;
  border: 1px solid var(--line);
  background: var(--panel-soft);
  color: var(--muted);
  font-size: 13px;
}

.hero-card .hero-title,
.hero-card .hero-subtitle,
.section-note,
.gr-markdown,
.gr-markdown p,
.gr-markdown li,
.gr-markdown h1,
.gr-markdown h2,
.gr-markdown h3,
.gr-block-label,
label,
legend,
span,
td,
th {
        color: var(--ink) !important;
}

.hero-subtitle,
.section-note,
.footer-tip {
    color: #000000 !important;
}

.gradio-container .tabs {
    border: none !important;
    background: transparent !important;
}

.gradio-container .tabs button,
button[role="tab"] {
    background: transparent !important;
    color: #000000 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    font-weight: 500 !important;
    padding: 10px 14px !important;
}

.gradio-container .tabs button.selected,
button[role="tab"][aria-selected="true"] {
    color: #000000 !important;
    border-bottom-color: var(--accent) !important;
}

.gr-button,
button {
    border-radius: 6px !important;
    box-shadow: none !important;
    font-weight: 500 !important;
}

.gr-button-primary {
    background: #f6f8fa !important;
    border: 1px solid var(--line) !important;
    color: #000000 !important;
}

.gr-button-primary:hover {
    background: #eef2f6 !important;
}

.gr-button-secondary {
    background: #f6f8fa !important;
        color: var(--ink) !important;
        border: 1px solid var(--line) !important;
}

.danger-btn,
.danger-btn button,
.danger-btn [role="button"] {
    background: #fff5f5 !important;
    color: #000000 !important;
    border: 1px solid #f1c0c0 !important;
}

.danger-btn:hover,
.danger-btn button:hover,
.danger-btn [role="button"]:hover {
    background: #ffe3e3 !important;
}

.run-green-btn,
.run-green-btn button,
.run-green-btn [role="button"] {
    background: #e8f5e9 !important;
    color: #0f5132 !important;
    border: 1px solid #b7dfc2 !important;
}

.run-green-btn:hover,
.run-green-btn button:hover,
.run-green-btn [role="button"]:hover {
    background: #d7efda !important;
}

.gr-button-secondary,
.gr-button-secondary * {
    color: var(--ink) !important;
}

input,
textarea,
select,
.gr-textbox,
.gr-dropdown,
.gr-code,
.gr-dataframe,
.cm-editor {
    color: var(--ink) !important;
    background: #ffffff !important;
}

input[type="checkbox"] {
    -webkit-appearance: checkbox !important;
    appearance: checkbox !important;
    accent-color: var(--accent) !important;
    width: 16px !important;
    height: 16px !important;
    cursor: pointer !important;
}

input[type="checkbox"]:checked {
    accent-color: var(--accent) !important;
}

input[type="checkbox"]:focus-visible {
    outline: 2px solid var(--accent) !important;
    outline-offset: 2px !important;
}

.gradio-container .gr-checkbox,
.gradio-container .gr-checkbox label,
.gradio-container .gr-checkbox span {
    cursor: pointer !important;
}

.gradio-container [role="checkbox"] {
    border: 1px solid var(--line) !important;
    border-radius: 4px !important;
    background: #ffffff !important;
}

.gradio-container [role="checkbox"][aria-checked="true"] {
    border-color: var(--accent) !important;
    background: var(--accent) !important;
}

.gradio-container [role="checkbox"][aria-checked="true"] * {
    color: #ffffff !important;
}

input::placeholder,
textarea::placeholder {
    color: #8c959f !important;
}

.gr-textbox input,
.gr-textbox textarea,
.gr-dropdown input,
.gr-code,
.cm-editor,
.cm-content,
.cm-line {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif !important;
}

.gr-code,
.cm-editor,
pre,
code {
    font-family: ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace !important;
}

.gr-textbox input,
.gr-textbox textarea,
.gr-dropdown input,
.cm-editor,
.gr-code,
.gr-code *,
.cm-content,
.cm-line {
    border-radius: 6px !important;
    color: var(--ink) !important;
}

.gr-dataframe table {
    border-collapse: collapse !important;
    background: #ffffff !important;
}

.gr-dataframe,
.gr-dataframe * {
    background: #ffffff !important;
    color: #000000 !important;
}

.gr-dataframe label,
.gr-dataframe .gr-block-label,
.gr-dataframe .label-wrap,
.gr-dataframe .label-wrap *,
.gr-dataframe .table-wrap,
.gr-dataframe .table-wrap *,
.gr-dataframe .container,
.gr-dataframe .container * {
    background: #ffffff !important;
    color: #000000 !important;
}

.gr-dataframe .table-wrap,
.gr-dataframe .table-container,
.gr-dataframe .wrap,
.gr-dataframe .cell-wrap,
.gr-dataframe .scrollable,
[data-testid="dataframe"],
[data-testid="dataframe"] * {
    background: #ffffff !important;
    color: #000000 !important;
}

.gr-dataframe th,
.gr-dataframe td {
    border: 1px solid var(--line) !important;
    padding: 8px 12px !important;
    color: var(--ink) !important;
}

.gr-dataframe th {
    background: #ffffff !important;
    color: #000000 !important;
    font-weight: 600 !important;
}

.gr-dataframe td {
    background: #ffffff !important;
    color: #000000 !important;
}

.gr-dataframe tbody tr {
    background: #ffffff !important;
}

.gr-dataframe thead,
.gr-dataframe tbody,
.gr-dataframe tr,
.gr-dataframe tbody tr:nth-child(odd),
.gr-dataframe tbody tr:nth-child(even) {
    background: #ffffff !important;
    color: #000000 !important;
}

.gr-dropdown,
.gr-textbox,
.gr-code,
.gr-dataframe,
.cm-editor,
.gr-form,
.gr-group,
.block {
    overflow: hidden;
}

.gr-dropdown,
.gr-dropdown *,
.gr-dropdown .wrap,
.gr-dropdown .wrap *,
.gr-dropdown .secondary-wrap,
.gr-dropdown .secondary-wrap *,
.gr-dropdown .token,
.gr-dropdown .token *,
.gr-dropdown input,
.gr-dropdown button,
.gr-dropdown [role="listbox"],
.gr-dropdown [role="option"],
[data-testid="dropdown"],
[data-testid="dropdown"] * {
    background: var(--soft-yellow) !important;
    color: #000000 !important;
}

[role="listbox"],
[role="listbox"] *,
[role="option"],
[role="option"] *,
ul[role="listbox"],
ul[role="listbox"] *,
li[role="option"],
li[role="option"] * {
    background: var(--soft-yellow) !important;
    color: #000000 !important;
    border-color: var(--line) !important;
}

[role="option"][aria-selected="true"],
li[role="option"][aria-selected="true"] {
    background: #fff2a8 !important;
    color: #000000 !important;
}

[role="option"][aria-selected="true"] *,
li[role="option"][aria-selected="true"] * {
    color: #000000 !important;
}

[data-headlessui-state],
[data-headlessui-state] * {
    color: #000000 !important;
}

.gr-dropdown {
    border: 1px solid var(--line) !important;
    border-radius: 6px !important;
}

.gr-code,
.gr-code *,
.cm-editor,
.cm-scroller,
.cm-content,
.cm-line,
.cm-gutters,
.cm-gutter,
.cm-activeLine,
.cm-activeLineGutter,
[data-testid="code"],
[data-testid="code"] * {
    background: var(--soft-yellow) !important;
    color: #000000 !important;
}

.gr-code button,
.gr-code [role="button"],
.gr-code .icon-btn,
.gr-code .label-wrap,
.gr-code .label-wrap * {
    background: #fff2a8 !important;
    color: #000000 !important;
    border-color: var(--line) !important;
}

.results-code-white,
.results-code-white *,
.results-code-white .cm-editor,
.results-code-white .cm-scroller,
.results-code-white .cm-content,
.results-code-white .cm-line,
.results-code-white .cm-gutters,
.results-code-white .cm-gutter,
.results-code-white [data-testid="code"],
.results-code-white [data-testid="code"] * {
    background: #ffffff !important;
    color: #000000 !important;
}

.gr-markdown,
.gr-markdown p,
.gr-markdown li,
.gr-markdown h1,
.gr-markdown h2,
.gr-markdown h3,
label {
    color: var(--ink) !important;
}

.gr-markdown h1,
.gr-markdown h2,
.gr-markdown h3 {
    font-weight: 600 !important;
}

.gr-markdown p,
.gr-markdown li,
.footer-tip {
    color: #000000 !important;
}

.gr-form > .form,
.gr-group {
    gap: 12px !important;
}

.footer-tip {
  color: var(--muted);
  font-size: 12px;
}

.task-table-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: #ffffff;
}

.task-table {
    width: 100%;
    border-collapse: collapse;
    background: #ffffff;
}

.task-table th,
.task-table td {
    border: 1px solid var(--line);
    padding: 8px 10px;
    text-align: left;
    color: #000000;
    background: #ffffff;
    font-size: 13px;
    white-space: nowrap;
}

.task-table th {
    font-weight: 600;
}

.task-selector-scroll [role="listbox"],
.task-selector-scroll ul[role="listbox"],
.task-selector-scroll .options {
    max-height: 340px !important;
    overflow-y: auto !important;
}

/* 2026 refresh: cleaner hierarchy and less visual noise */
body,
.gradio-container,
.gradio-container .main {
    background:
        radial-gradient(circle at 8% 0%, #d9ecff 0%, transparent 28%),
        radial-gradient(circle at 92% 0%, #ffe6cf 0%, transparent 30%),
        #f5f8fc !important;
}

.app-shell {
    margin-bottom: 12px;
}

.hero-card {
    border-radius: 14px !important;
    border: 1px solid #d0dff2 !important;
    background: linear-gradient(135deg, #f9fcff 0%, #f2f8ff 52%, #fef8f2 100%) !important;
    box-shadow: 0 8px 26px rgba(15, 23, 42, 0.06) !important;
}

.section-note {
    border-radius: 12px !important;
    border: 1px solid #d7e5f5 !important;
    background: #fbfdff !important;
    line-height: 1.55;
}

.gradio-container .tabs button,
button[role="tab"] {
    border-radius: 10px !important;
    border: 1px solid transparent !important;
    margin-right: 8px;
    margin-bottom: 8px;
    background: #eef4fb !important;
}

.gradio-container .tabs button.selected,
button[role="tab"][aria-selected="true"] {
    border-color: #90b4dd !important;
    background: #dcecff !important;
    color: #0b2f5e !important;
}

.gr-button,
button {
    border-radius: 10px !important;
    transition: all 0.2s ease !important;
}

.gr-button-primary {
    background: linear-gradient(135deg, #1d75d8 0%, #165cb2 100%) !important;
    border-color: #165cb2 !important;
    color: #ffffff !important;
}

.gr-button-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(22, 92, 178, 0.22) !important;
}

.gr-group,
.block,
.gr-box,
.gr-form {
    border-radius: 12px !important;
}

.gr-accordion {
    border: 1px solid #d5e2f2 !important;
    border-radius: 12px !important;
    background: #fcfdff !important;
}

.gr-accordion > button,
.gr-accordion summary {
    font-weight: 600 !important;
}

.footer-tip {
    font-size: 13px;
    color: #264a77 !important;
}
"""


FORM_FIELD_NAMES = [
    "task_name",
    "description",
    "source_name",
    "prefix",
    "home_url_list",
    "url_xpath",
    "title_xpath",
    "content_xpath",
    "home_date_xpath",
    "date_xpath",
    "image_xpath",
    "detail_image_xpath",
    "url_limit",
    "list_retry_count",
    "list_retry_sleep_seconds",
    "detail_retry_count",
    "detail_retry_sleep_seconds",
    "home_request_delay_seconds",
    "home_request_delay_jitter_seconds",
    "detail_request_delay_seconds",
    "detail_request_delay_jitter_seconds",
    "fetch_timeout",
    "login_enabled",
    "login_username",
    "login_password",
    "playwright_login_url",
    "playwright_login_entry_xpath",
    "playwright_login_username_xpath",
    "playwright_login_password_xpath",
    "playwright_login_submit_xpath",
    "playwright_login_success_xpath",
    "playwright_login_timeout",
    "playwright_headless",
    "enable_content_image_placeholder",
    "content_root_xpath",
    "content_image_xpath",
    "content_image_placeholder_template",
    "append_content_image_mapping",
    "category",
    "min_content_length",
    "max_content_length",
    "dedupe_urls",
    "home_wait_xpath",
    "detail_wait_xpath",
    "source_language",
    "source_map",
    "content_joiner",
    "default_image_url",
    "date_patterns",
    "schedule_type",
    "cron_expression",
    "interval_seconds",
    "schedule_enabled",
]


def api_request(method: str, path: str, payload: Dict[str, Any] | None = None, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    response = requests.request(method=method, url=url, json=payload, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def stringify_lines(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, list):
        return "\n".join(str(item) for item in values if str(item).strip())
    return str(values)


def stringify_xpath(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())
    return str(value)


def parse_multiline_list(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").splitlines() if item.strip()]


def parse_xpath_value(value: str) -> str | List[str] | None:
    items = parse_multiline_list(value)
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    return items


def parse_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_checkbox_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on", "y"}


def parse_json_object(value: str, field_name: str) -> Dict[str, str]:
    raw = str(value or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} JSON 解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{field_name} 必须是 JSON 对象")
    return {str(key): str(val) for key, val in data.items()}


def normalize_task_rows(tasks: List[Dict[str, Any]]) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for item in tasks:
        rows.append(
            [
                item.get("task_name", ""),
                item.get("source_name", ""),
                item.get("last_run_at", "") or "-",
                item.get("last_status", "") or "idle",
                item.get("schedule_type", "manual"),
                "已启用" if item.get("schedule_enabled") else "未启用",
                str(item.get("id", "")),
            ]
        )
    return rows


def render_task_table_html(tasks: List[Dict[str, Any]]) -> str:
    headers = ["任务标题", "来源", "最近执行时间", "最近状态", "调度类型", "调度开关", "task_id"]
    if not tasks:
        return (
            '<div class="task-table-wrap">'
            '<table class="task-table">'
            '<thead><tr>'
            + "".join(f"<th>{escape(header)}</th>" for header in headers)
            + "</tr></thead>"
            '<tbody><tr><td colspan="7">暂无任务</td></tr></tbody>'
            '</table></div>'
        )

    body_rows = []
    for item in tasks:
        row = [
            item.get("task_name", ""),
            item.get("source_name", ""),
            item.get("last_run_at", "") or "-",
            item.get("last_status", "") or "idle",
            item.get("schedule_type", "manual"),
            "已启用" if item.get("schedule_enabled") else "未启用",
            str(item.get("id", "")),
        ]
        body_rows.append("<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>")

    return (
        '<div class="task-table-wrap">'
        '<table class="task-table">'
        '<thead><tr>'
        + "".join(f"<th>{escape(header)}</th>" for header in headers)
        + "</tr></thead>"
        + "<tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def truncate_text(value: Any, max_length: int = 120) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def render_inserted_data_table_html(records: List[Dict[str, Any]]) -> str:
    headers = [
        "article_id",
        "标题",
        "中文标题",
        "详情日期",
        "更新时间",
        "来源中文名",
        "一级分类",
        "二级分类",
        "是否翻译",
        "详情链接",
        "正文预览",
    ]
    if not records:
        return (
            '<div class="task-table-wrap">'
            '<table class="task-table">'
            '<thead><tr>'
            + "".join(f"<th>{escape(header)}</th>" for header in headers)
            + "</tr></thead>"
            f'<tbody><tr><td colspan="{len(headers)}">暂无入库数据</td></tr></tbody>'
            '</table></div>'
        )

    body_rows = []
    for item in records:
        row = [
            item.get("article_id", ""),
            truncate_text(item.get("detail_title"), 80),
            truncate_text(item.get("detail_title_cn"), 80),
            item.get("detail_date", "") or "-",
            item.get("update_time", "") or "-",
            item.get("news_source_name_cn", "") or "-",
            item.get("class_level_1", "") or "-",
            item.get("class_level_2", "") or "-",
            item.get("is_translated", "") or "-",
            truncate_text(item.get("detail_url"), 100),
            truncate_text(item.get("detail_contents_cn") or item.get("detail_contents"), 160),
        ]
        body_rows.append("<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>")

    return (
        '<div class="task-table-wrap">'
        '<table class="task-table">'
        '<thead><tr>'
        + "".join(f"<th>{escape(header)}</th>" for header in headers)
        + "</tr></thead>"
        + "<tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def refresh_tasks(page: int = 1, page_size: int = 20) -> Tuple[str, Dict[str, Any], str, int, str]:
    try:
        safe_page_size = int(page_size) if page_size else 20
        safe_page_size = max(1, min(safe_page_size, 200))
        safe_page = int(page) if page else 1
        safe_page = max(1, safe_page)

        result = api_request("GET", "/v1/crawler/tasks", params={"page": safe_page, "page_size": safe_page_size})
        tasks = result.get("data", [])
        current_page = int(result.get("page") or safe_page)
        total = int(result.get("total") or 0)
        total_pages = int(result.get("total_pages") or 0)
        choices = [(f"{item.get('task_name')} | {item.get('source_name')}", str(item.get("id"))) for item in tasks]
        default_value = choices[0][1] if choices else None
        page_text = f"第 {current_page} / {total_pages if total_pages > 0 else 1} 页，共 {total} 条"
        return (
            render_task_table_html(tasks),
            gr.update(choices=choices, value=default_value),
            f"已加载 {len(tasks)} 个任务",
            current_page,
            page_text,
        )
    except Exception as exc:
        return render_task_table_html([]), gr.update(choices=[], value=None), f"任务加载失败: {exc}", max(1, int(page or 1)), "分页信息不可用"


def change_task_page(current_page: int, page_size: int, direction: str) -> Tuple[str, Dict[str, Any], str, int, str]:
    safe_current = max(1, int(current_page or 1))
    if direction == "prev":
        target_page = max(1, safe_current - 1)
    elif direction == "next":
        target_page = safe_current + 1
    else:
        target_page = safe_current
    return refresh_tasks(page=target_page, page_size=page_size)


def refresh_tasks_from_page_size(page_size: int) -> Tuple[str, Dict[str, Any], str, int, str]:
    return refresh_tasks(page=1, page_size=page_size)


def refresh_inserted_data(page: int = 1, page_size: int = 20) -> Tuple[str, str, int, str, str]:
    try:
        safe_page_size = int(page_size) if page_size else 20
        safe_page_size = max(1, min(safe_page_size, 200))
        safe_page = int(page) if page else 1
        safe_page = max(1, safe_page)

        result = api_request("GET", "/v1/crawler/inserted-data", params={"page": safe_page, "page_size": safe_page_size})
        records = result.get("data", [])
        current_page = int(result.get("page") or safe_page)
        total = int(result.get("total") or 0)
        total_pages = int(result.get("total_pages") or 0)
        page_text = f"第 {current_page} / {total_pages if total_pages > 0 else 1} 页，共 {total} 条"
        return (
            render_inserted_data_table_html(records),
            f"已加载 {len(records)} 条入库数据",
            current_page,
            page_text,
            pretty_json(result),
        )
    except Exception as exc:
        return render_inserted_data_table_html([]), f"入库数据加载失败: {exc}", max(1, int(page or 1)), "分页信息不可用", pretty_json({"error": str(exc)})


def change_inserted_data_page(current_page: int, page_size: int, direction: str) -> Tuple[str, str, int, str, str]:
    safe_current = max(1, int(current_page or 1))
    if direction == "prev":
        target_page = max(1, safe_current - 1)
    elif direction == "next":
        target_page = safe_current + 1
    else:
        target_page = safe_current
    return refresh_inserted_data(page=target_page, page_size=page_size)


def refresh_inserted_data_from_page_size(page_size: int) -> Tuple[str, str, int, str, str]:
    return refresh_inserted_data(page=1, page_size=page_size)


def load_task_summary(task_id: str) -> str:
    if not task_id:
        return "请选择任务后查看概览。"
    try:
        result = api_request("GET", f"/v1/crawler/tasks/{task_id}")
        task = result.get("data", {})
        return (
            f"### {task.get('task_name', '-')}\n"
            f"来源：{task.get('source_name', '-')}\n\n"
            f"最近执行：{task.get('last_run_at') or '-'}\n\n"
            f"最近状态：{task.get('last_status') or '-'}\n\n"
            f"调度方式：{task.get('schedule_type') or '-'}\n\n"
            f"任务 ID：{task.get('id') or '-'}"
        )
    except Exception as exc:
        return f"任务概览加载失败: {exc}"


def load_task_execution_results(task_id: str) -> str:
    if not task_id:
        return pretty_json({"message": "请选择任务"})
    try:
        executions_result = api_request("GET", f"/v1/crawler/tasks/{task_id}/executions", params={"limit": 1})
        executions = executions_result.get("data") or []
        if not executions:
            return pretty_json({"message": "当前任务暂无执行记录"})

        latest_execution = executions[0]
        celery_task_id = latest_execution.get("celery_task_id")
        if not celery_task_id:
            return pretty_json({"message": "最近执行记录缺少 celery_task_id", "execution": latest_execution})

        result = api_request("GET", f"/v1/crawler/executions/{celery_task_id}/results")
        return pretty_json(result)
    except Exception as exc:
        return pretty_json({"error": f"执行结果加载失败: {exc}"})


def task_to_form_values(task: Dict[str, Any], include_task_id: bool = False) -> Tuple[Any, ...]:
    values: List[Any] = []
    if include_task_id:
        values.append(str(task.get("id", "")))
    values.extend(
        [
            task.get("task_name", ""),
            task.get("description", "") or "",
            task.get("source_name", ""),
            task.get("prefix", "") or "",
            stringify_lines(task.get("home_url_list")),
            stringify_xpath(task.get("url_xpath")),
            stringify_xpath(task.get("title_xpath")),
            stringify_xpath(task.get("content_xpath")),
            stringify_xpath(task.get("home_date_xpath")),
            stringify_xpath(task.get("date_xpath")),
            stringify_xpath(task.get("image_xpath")),
            stringify_xpath(task.get("detail_image_xpath")),
            int(task.get("url_limit", 10) or 10),
            int(task.get("list_retry_count", 1) or 0),
            int(task.get("list_retry_sleep_seconds", 3) or 0),
            int(task.get("detail_retry_count", 0) or 0),
            int(task.get("detail_retry_sleep_seconds", 2) or 0),
            float(task.get("home_request_delay_seconds", 0) or 0),
            float(task.get("home_request_delay_jitter_seconds", 0) or 0),
            float(task.get("detail_request_delay_seconds", 0) or 0),
            float(task.get("detail_request_delay_jitter_seconds", 0) or 0),
            int(task.get("fetch_timeout", 360) or 360),
            bool(task.get("login_enabled", False)),
            task.get("login_username", "") or "",
            task.get("login_password", "") or "",
            task.get("playwright_login_url", "") or "",
            task.get("playwright_login_entry_xpath", "") or "",
            task.get("playwright_login_username_xpath", "") or "",
            task.get("playwright_login_password_xpath", "") or "",
            task.get("playwright_login_submit_xpath", "") or "",
            task.get("playwright_login_success_xpath", "") or "",
            int(task.get("playwright_login_timeout", 60) or 60),
            bool(task.get("playwright_headless", True)),
            bool(task.get("enable_content_image_placeholder", False)),
            stringify_xpath(task.get("content_root_xpath")),
            stringify_xpath(task.get("content_image_xpath")),
            task.get("content_image_placeholder_template", "![图片{index}]({url})") or "![图片{index}]({url})",
            bool(task.get("append_content_image_mapping", False)),
            task.get("category", "") or "",
            int(task.get("min_content_length", 0) or 0),
            int(task.get("max_content_length", 0) or 0),
            bool(task.get("dedupe_urls", False)),
            stringify_xpath(task.get("home_wait_xpath")),
            stringify_xpath(task.get("detail_wait_xpath")),
            task.get("source_language", "auto") or "auto",
            pretty_json(task.get("source_map", {})),
            task.get("content_joiner", " ") or " ",
            task.get("default_image_url", "") or "",
            stringify_lines(task.get("date_patterns")),
            task.get("schedule_type", "manual") or "manual",
            task.get("cron_expression", "") or "",
            int(task.get("interval_seconds", 0) or 0),
            bool(task.get("schedule_enabled", False)),
        ]
    )
    return tuple(values)


def get_default_form_values(include_task_id: bool = False) -> Tuple[Any, ...]:
    return task_to_form_values(DEFAULT_TASK_TEMPLATE, include_task_id=include_task_id)


def load_task_for_edit(task_id: str) -> Tuple[Any, ...]:
    if not task_id:
        return (*get_default_form_values(include_task_id=True), "请选择任务后再编辑")
    try:
        result = api_request("GET", f"/v1/crawler/tasks/{task_id}")
        task = result.get("data", {})
        return (*task_to_form_values(task, include_task_id=True), f"已加载任务 {task.get('task_name', '')} 到编辑表单")
    except Exception as exc:
        return (*get_default_form_values(include_task_id=True), f"加载编辑表单失败: {exc}")


def prepare_create_form() -> Tuple[Any, ...]:
    return (*get_default_form_values(include_task_id=False), "创建表单已填充示例模板")


def build_payload_from_form(*values: Any) -> Dict[str, Any]:
    form = dict(zip(FORM_FIELD_NAMES, values))
    interval_value = form.get("interval_seconds")
    interval_seconds = int(interval_value) if interval_value not in (None, "") else None
    min_content_length = max(0, int(form.get("min_content_length") or 0))
    max_content_length = max(0, int(form.get("max_content_length") or 0))
    if max_content_length > 0 and max_content_length < min_content_length:
        raise ValueError("max_content_length 不能小于 min_content_length")
    return {
        "task_name": str(form.get("task_name", "") or "").strip(),
        "description": parse_optional_text(form.get("description")),
        "source_name": str(form.get("source_name", "") or "").strip(),
        "prefix": parse_optional_text(form.get("prefix")),
        "home_url_list": parse_multiline_list(str(form.get("home_url_list", "") or "")),
        "url_xpath": parse_xpath_value(str(form.get("url_xpath", "") or "")),
        "title_xpath": parse_xpath_value(str(form.get("title_xpath", "") or "")),
        "content_xpath": parse_xpath_value(str(form.get("content_xpath", "") or "")),
        "home_date_xpath": parse_xpath_value(str(form.get("home_date_xpath", "") or "")),
        "date_xpath": parse_xpath_value(str(form.get("date_xpath", "") or "")),
        "image_xpath": parse_xpath_value(str(form.get("image_xpath", "") or "")),
        "detail_image_xpath": parse_xpath_value(str(form.get("detail_image_xpath", "") or "")),
        "url_limit": int(form.get("url_limit") or 10),
        "list_retry_count": int(form.get("list_retry_count") or 0),
        "list_retry_sleep_seconds": int(form.get("list_retry_sleep_seconds") or 0),
        "detail_retry_count": int(form.get("detail_retry_count") or 0),
        "detail_retry_sleep_seconds": int(form.get("detail_retry_sleep_seconds") or 0),
        "home_request_delay_seconds": float(form.get("home_request_delay_seconds") or 0),
        "home_request_delay_jitter_seconds": float(form.get("home_request_delay_jitter_seconds") or 0),
        "detail_request_delay_seconds": float(form.get("detail_request_delay_seconds") or 0),
        "detail_request_delay_jitter_seconds": float(form.get("detail_request_delay_jitter_seconds") or 0),
        "fetch_timeout": int(form.get("fetch_timeout") or 360),
        "login_enabled": parse_checkbox_value(form.get("login_enabled")),
        "login_username": str(form.get("login_username", "") or "").strip(),
        "login_password": str(form.get("login_password", "") or "").strip(),
        "playwright_login_url": parse_optional_text(form.get("playwright_login_url")),
        "playwright_login_entry_xpath": parse_optional_text(form.get("playwright_login_entry_xpath")),
        "playwright_login_username_xpath": parse_optional_text(form.get("playwright_login_username_xpath")),
        "playwright_login_password_xpath": parse_optional_text(form.get("playwright_login_password_xpath")),
        "playwright_login_submit_xpath": parse_optional_text(form.get("playwright_login_submit_xpath")),
        "playwright_login_success_xpath": parse_optional_text(form.get("playwright_login_success_xpath")),
        "playwright_login_timeout": int(form.get("playwright_login_timeout") or 60),
        "playwright_headless": parse_checkbox_value(form.get("playwright_headless")),
        "enable_content_image_placeholder": parse_checkbox_value(form.get("enable_content_image_placeholder")),
        "content_root_xpath": parse_xpath_value(str(form.get("content_root_xpath", "") or "")),
        "content_image_xpath": parse_xpath_value(str(form.get("content_image_xpath", "") or "")),
        "content_image_placeholder_template": str(
            form.get("content_image_placeholder_template", "![图片{index}]({url})") or "![图片{index}]({url})"
        ).strip(),
        "append_content_image_mapping": parse_checkbox_value(form.get("append_content_image_mapping")),
        "category": str(form.get("category", "") or "").strip(),
        "min_content_length": min_content_length,
        "max_content_length": max_content_length,
        "dedupe_urls": parse_checkbox_value(form.get("dedupe_urls")),
        "home_wait_xpath": parse_xpath_value(str(form.get("home_wait_xpath", "") or "")),
        "detail_wait_xpath": parse_xpath_value(str(form.get("detail_wait_xpath", "") or "")),
        "source_language": str(form.get("source_language", "auto") or "auto").strip(),
        "source_map": parse_json_object(str(form.get("source_map", "") or ""), "source_map"),
        "content_joiner": str(form.get("content_joiner", " ") or " "),
        "default_image_url": parse_optional_text(form.get("default_image_url")),
        "date_patterns": parse_multiline_list(str(form.get("date_patterns", "") or "")),
        "schedule_type": str(form.get("schedule_type", "manual") or "manual").strip(),
        "cron_expression": parse_optional_text(form.get("cron_expression")),
        "interval_seconds": interval_seconds,
        "schedule_enabled": parse_checkbox_value(form.get("schedule_enabled")),
    }


def submit_task_form(action: str, task_id: str, selected_task_id: str, *values: Any) -> Tuple[str, str]:
    try:
        payload = build_payload_from_form(*values)
    except ValueError as exc:
        return "", str(exc)
    try:
        if action == "create":
            result = api_request("POST", "/v1/crawler/tasks", payload=payload)
            return pretty_json(result), "任务创建成功"
        if action == "update":
            effective_task_id = parse_optional_text(task_id) or parse_optional_text(selected_task_id)
            if not effective_task_id:
                return "", "更新任务前请先加载任务"
            result = api_request("PUT", f"/v1/crawler/tasks/{effective_task_id}", payload=payload)
            return pretty_json(result), "任务更新成功"
        return "", "未知操作"
    except Exception as exc:
        return "", f"提交失败: {exc}"


def trigger_task_action(action: str, task_id: str) -> str:
    if not task_id:
        return "请选择任务"
    try:
        if action == "run":
            result = api_request("POST", f"/v1/crawler/tasks/{task_id}/run")
            return result.get("message") or "任务已提交执行"
        if action == "delete":
            result = api_request("DELETE", f"/v1/crawler/tasks/{task_id}")
            return result.get("message") or "任务已删除"
        return "未知操作"
    except Exception as exc:
        return f"操作失败: {exc}"


def build_task_form(section_title: str, section_subtitle: str, include_task_id: bool = False) -> Dict[str, gr.components.Component]:
    form: Dict[str, gr.components.Component] = {}
    gr.Markdown(f"## {section_title}")
    gr.Markdown(section_subtitle)
    with gr.Group():
        gr.Markdown(
            """
            <div class="section-note">
              <strong>快速上手：</strong>先填写基础信息、URL 与三个核心 XPath（列表链接 / 标题 / 正文）。
              其余参数按需展开，避免一次性处理全部配置造成认知负担。
            </div>
            """
        )
        if include_task_id:
            form["task_id"] = gr.Textbox(label="任务 ID", interactive=False)

        with gr.Accordion("1) 基础信息（必填优先）", open=True):
            with gr.Row():
                form["task_name"] = gr.Textbox(label="任务标题", placeholder="例如：jmd-crawler")
                form["source_name"] = gr.Textbox(label="来源标识", placeholder="例如：jmd")
                form["source_language"] = gr.Textbox(label="来源语言", value="auto", placeholder="auto / zh / en / ja ...")
            with gr.Row():
                form["category"] = gr.Textbox(label="业务分类（可选）", placeholder="例如：shipping-news")
                form["prefix"] = gr.Textbox(label="URL 前缀", placeholder="例如：https://www.jmd.co.jp")
            form["description"] = gr.Textbox(label="任务描述", lines=2)
            form["home_url_list"] = gr.Textbox(label="首页 URL 列表", lines=3, placeholder="每行一个 URL")

        with gr.Accordion("2) 解析规则（XPath）", open=True):
            with gr.Row():
                form["url_xpath"] = gr.Textbox(label="列表链接 XPath", lines=3)
                form["title_xpath"] = gr.Textbox(label="标题 XPath", lines=3)
            with gr.Row():
                form["content_xpath"] = gr.Textbox(label="正文 XPath", lines=4)
                form["home_date_xpath"] = gr.Textbox(label="列表日期 XPath", lines=4)
            with gr.Row():
                form["date_xpath"] = gr.Textbox(label="详情日期 XPath", lines=3)
                form["image_xpath"] = gr.Textbox(label="列表图片 XPath", lines=3)
                form["detail_image_xpath"] = gr.Textbox(label="详情图片 XPath", lines=3)
            with gr.Row():
                form["home_wait_xpath"] = gr.Textbox(label="首页等待 XPath", lines=2)
                form["detail_wait_xpath"] = gr.Textbox(label="详情等待 XPath", lines=2)

        with gr.Accordion("3) 抓取策略（稳定性与长度过滤）", open=False):
            with gr.Row():
                form["url_limit"] = gr.Number(label="抓取上限", value=10, precision=0)
                form["fetch_timeout"] = gr.Number(label="抓取超时秒", value=360, precision=0)
                form["dedupe_urls"] = gr.Checkbox(label="URL 去重", value=False, interactive=True)
            with gr.Row():
                form["list_retry_count"] = gr.Number(label="列表重试次数", value=1, precision=0)
                form["list_retry_sleep_seconds"] = gr.Number(label="列表重试间隔秒", value=3, precision=0)
                form["detail_retry_count"] = gr.Number(label="详情重试次数", value=0, precision=0)
                form["detail_retry_sleep_seconds"] = gr.Number(label="详情重试间隔秒", value=2, precision=0)
            with gr.Row():
                form["home_request_delay_seconds"] = gr.Number(label="首页固定延迟秒", value=0, precision=2)
                form["home_request_delay_jitter_seconds"] = gr.Number(label="首页抖动秒", value=0, precision=2)
                form["detail_request_delay_seconds"] = gr.Number(label="详情固定延迟秒", value=0, precision=2)
                form["detail_request_delay_jitter_seconds"] = gr.Number(label="详情抖动秒", value=0, precision=2)
            with gr.Row():
                form["min_content_length"] = gr.Number(label="正文最小长度", value=0, precision=0)
                form["max_content_length"] = gr.Number(label="正文最大长度", value=0, precision=0)

        with gr.Accordion("4) 调度配置", open=False):
            with gr.Row():
                form["schedule_type"] = gr.Dropdown(label="调度类型", choices=["manual", "interval", "cron"], value="manual")
                form["interval_seconds"] = gr.Number(label="间隔秒数", value=0, precision=0)
                form["cron_expression"] = gr.Textbox(label="Cron 表达式")
                form["schedule_enabled"] = gr.Checkbox(label="启用调度", value=False, interactive=True)

        with gr.Accordion("5) 来源映射与日期格式", open=False):
            with gr.Row():
                form["content_joiner"] = gr.Textbox(label="正文拼接符", value=" ")
                form["default_image_url"] = gr.Textbox(label="默认图片 URL")
            with gr.Row():
                form["source_map"] = gr.Textbox(label="来源映射 JSON", lines=8, value="{}")
                form["date_patterns"] = gr.Textbox(label="日期格式列表", lines=6, placeholder="每行一个日期格式")

        with gr.Accordion("6) 高级能力：登录态与图文占位", open=False):
            with gr.Row():
                form["login_enabled"] = gr.Checkbox(label="启用 Playwright 登录态", value=False, interactive=True)
                form["playwright_headless"] = gr.Checkbox(label="Playwright 无头模式", value=True, interactive=True)
                form["playwright_login_timeout"] = gr.Number(label="登录超时秒", value=60, precision=0)
            with gr.Row():
                form["login_username"] = gr.Textbox(label="登录用户名")
                form["login_password"] = gr.Textbox(label="登录密码", type="password")
                form["playwright_login_url"] = gr.Textbox(label="登录页 URL")
            with gr.Row():
                form["playwright_login_entry_xpath"] = gr.Textbox(label="登录入口 XPath", lines=2)
                form["playwright_login_username_xpath"] = gr.Textbox(label="用户名 XPath", lines=2)
                form["playwright_login_password_xpath"] = gr.Textbox(label="密码 XPath", lines=2)
            with gr.Row():
                form["playwright_login_submit_xpath"] = gr.Textbox(label="提交按钮 XPath", lines=2)
                form["playwright_login_success_xpath"] = gr.Textbox(label="登录成功等待 XPath", lines=2)
            with gr.Row():
                form["enable_content_image_placeholder"] = gr.Checkbox(label="正文启用图片 Markdown 占位", value=False, interactive=True)
                form["append_content_image_mapping"] = gr.Checkbox(label="正文追加图片映射", value=False, interactive=True)
            with gr.Row():
                form["content_root_xpath"] = gr.Textbox(label="正文根节点 XPath", lines=2)
                form["content_image_xpath"] = gr.Textbox(label="正文图片 XPath", value=".//img/@src", lines=2)
            with gr.Row():
                form["content_image_placeholder_template"] = gr.Textbox(
                    label="图片占位模板",
                    value="![图片{index}]({url})",
                )

        with gr.Accordion("使用建议", open=False):
            gr.Markdown(
                """
                - 常规站点：只需先完成 1) + 2) + 3) 的核心配置。
                - 需要定时：再填写 4) 调度配置。
                - 登录墙或图文混排：再展开 6) 高级能力。
                - 推荐先点击“填充示例”，再按站点差异做最小改动。
                """
            )
    return form


def get_form_outputs(form: Dict[str, gr.components.Component], include_task_id: bool = False) -> List[gr.components.Component]:
    outputs: List[gr.components.Component] = []
    if include_task_id:
        outputs.append(form["task_id"])
    for name in FORM_FIELD_NAMES:
        outputs.append(form[name])
    return outputs


with gr.Blocks(title=APP_TITLE, css=THEME_CSS) as app:
    gr.HTML(
        f"""
        <div class="app-shell">
          <div class="hero-card">
            <div class="hero-title">{APP_TITLE}</div>
                        <p class="hero-subtitle">简洁任务面板。首页处理操作，创建页和编辑页统一使用表单。</p>
          </div>
          <div class="section-note">建议先启动 FastAPI 服务，再打开本控制台。所有操作都通过现有 /api/v1/crawler 接口完成。</div>
        </div>
        """
    )

    with gr.Tabs():
        with gr.Tab("首页"):
            gr.Markdown("## 任务列表")
            gr.Markdown("简约展示任务标题、最近执行时间，并在首页保留创建、编辑、删除和立刻执行入口。")
            with gr.Row():
                api_base_box = gr.Textbox(label="API Base URL", value=API_BASE_URL, interactive=False)
                refresh_btn = gr.Button("刷新列表", variant="secondary", elem_classes=["results-code-white"])
                home_status = gr.Textbox(label="状态", value="等待加载", interactive=False)
            with gr.Row():
                prev_page_btn = gr.Button("上一页", variant="secondary", elem_classes=["results-code-white"])
                next_page_btn = gr.Button("下一页", variant="secondary", elem_classes=["results-code-white"])
                page_size_selector = gr.Dropdown(label="每页条数", choices=[1, 5, 10, 20, 50, 100], value=20, elem_classes=["results-code-white"])
                page_info = gr.Textbox(label="分页", value="第 1 / 1 页，共 0 条", interactive=False)
            current_page_state = gr.State(1)
            task_table = gr.HTML(value=render_task_table_html([]), label="Crawler Tasks")
            with gr.Row():
                task_selector = gr.Dropdown(label="当前任务", choices=[], value=None, allow_custom_value=True, elem_classes=["results-code-white", "task-selector-scroll"])
                run_btn = gr.Button("立刻执行", variant="primary", elem_classes=["run-green-btn"])
                delete_btn = gr.Button("删除任务", elem_classes=["danger-btn"])
            selected_task_summary = gr.Markdown("请选择任务后查看概览。")
            action_output = gr.Code(label="最近执行结果", language="json", interactive=False, value="{}", elem_classes=["results-code-white"])

        with gr.Tab("创建任务"):
            create_form = build_task_form("创建任务", "创建页面使用结构化表单，不再直接编辑整段 JSON。", include_task_id=False)
            with gr.Row():
                create_template_btn = gr.Button("填充示例", variant="secondary")
                create_submit_btn = gr.Button("提交创建", variant="primary")
            create_output = gr.Code(label="创建结果", language="json", interactive=False)
            create_status = gr.Textbox(label="创建状态", interactive=False)

        with gr.Tab("编辑任务"):
            with gr.Row():
                edit_load_btn = gr.Button("加载当前选中任务", variant="secondary")
                edit_submit_btn = gr.Button("保存修改", variant="primary")
            edit_form = build_task_form("编辑任务", "编辑页面与创建页面保持同一套表单字段。", include_task_id=True)
            edit_output = gr.Code(label="更新结果", language="json", interactive=False)
            edit_status = gr.Textbox(label="编辑状态", interactive=False)

        with gr.Tab("入库数据"):
            gr.Markdown("## 正式入库数据")
            gr.Markdown("分页展示库内 `ex_shipping_information` 表中的全部正式入库数据。")
            with gr.Row():
                inserted_refresh_btn = gr.Button("刷新数据", variant="secondary", elem_classes=["results-code-white"])
                inserted_status = gr.Textbox(label="状态", value="等待加载", interactive=False)
            with gr.Row():
                inserted_prev_page_btn = gr.Button("上一页", variant="secondary", elem_classes=["results-code-white"])
                inserted_next_page_btn = gr.Button("下一页", variant="secondary", elem_classes=["results-code-white"])
                inserted_page_size_selector = gr.Dropdown(label="每页条数", choices=[1, 5, 10, 20, 50, 100, 200], value=20, elem_classes=["results-code-white"])
                inserted_page_info = gr.Textbox(label="分页", value="第 1 / 1 页，共 0 条", interactive=False)
            inserted_current_page_state = gr.State(1)
            inserted_data_table = gr.HTML(value=render_inserted_data_table_html([]), label="Inserted Data")
            inserted_raw_output = gr.Code(label="接口原始响应", language="json", interactive=False, value="{}", elem_classes=["results-code-white"])

    gr.HTML('<div class="footer-tip">界面方向：干净、轻量、偏内部工具。首页看任务，表单页改配置。</div>')

    refresh_btn.click(
        fn=refresh_tasks,
        inputs=[current_page_state, page_size_selector],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )
    prev_page_btn.click(
        fn=change_task_page,
        inputs=[current_page_state, page_size_selector, gr.State("prev")],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )
    next_page_btn.click(
        fn=change_task_page,
        inputs=[current_page_state, page_size_selector, gr.State("next")],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )
    page_size_selector.change(
        fn=refresh_tasks_from_page_size,
        inputs=[page_size_selector],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )
    task_selector.change(fn=load_task_summary, inputs=[task_selector], outputs=[selected_task_summary])
    task_selector.change(fn=load_task_execution_results, inputs=[task_selector], outputs=[action_output])
    task_selector.change(fn=load_task_for_edit, inputs=[task_selector], outputs=[*get_form_outputs(edit_form, include_task_id=True), edit_status])

    edit_load_btn.click(fn=load_task_for_edit, inputs=[task_selector], outputs=[*get_form_outputs(edit_form, include_task_id=True), edit_status])

    run_btn.click(fn=trigger_task_action, inputs=[gr.State("run"), task_selector], outputs=[home_status])
    delete_btn.click(fn=trigger_task_action, inputs=[gr.State("delete"), task_selector], outputs=[home_status])
    run_btn.click(
        fn=refresh_tasks,
        inputs=[current_page_state, page_size_selector],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )
    delete_btn.click(
        fn=refresh_tasks,
        inputs=[current_page_state, page_size_selector],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )
    run_btn.click(fn=load_task_execution_results, inputs=[task_selector], outputs=[action_output])
    delete_btn.click(fn=load_task_execution_results, inputs=[task_selector], outputs=[action_output])

    create_template_btn.click(fn=prepare_create_form, outputs=[*get_form_outputs(create_form), create_status])
    create_submit_btn.click(
        fn=submit_task_form,
        inputs=[gr.State("create"), gr.State(""), gr.State(""), *get_form_outputs(create_form)],
        outputs=[create_output, create_status],
    )
    create_submit_btn.click(
        fn=refresh_tasks,
        inputs=[current_page_state, page_size_selector],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )

    edit_submit_btn.click(
        fn=submit_task_form,
        inputs=[gr.State("update"), edit_form["task_id"], task_selector, *get_form_outputs(edit_form)],
        outputs=[edit_output, edit_status],
    )
    edit_submit_btn.click(
        fn=refresh_tasks,
        inputs=[current_page_state, page_size_selector],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )

    inserted_refresh_btn.click(
        fn=refresh_inserted_data,
        inputs=[inserted_current_page_state, inserted_page_size_selector],
        outputs=[inserted_data_table, inserted_status, inserted_current_page_state, inserted_page_info, inserted_raw_output],
    )
    inserted_prev_page_btn.click(
        fn=change_inserted_data_page,
        inputs=[inserted_current_page_state, inserted_page_size_selector, gr.State("prev")],
        outputs=[inserted_data_table, inserted_status, inserted_current_page_state, inserted_page_info, inserted_raw_output],
    )
    inserted_next_page_btn.click(
        fn=change_inserted_data_page,
        inputs=[inserted_current_page_state, inserted_page_size_selector, gr.State("next")],
        outputs=[inserted_data_table, inserted_status, inserted_current_page_state, inserted_page_info, inserted_raw_output],
    )
    inserted_page_size_selector.change(
        fn=refresh_inserted_data_from_page_size,
        inputs=[inserted_page_size_selector],
        outputs=[inserted_data_table, inserted_status, inserted_current_page_state, inserted_page_info, inserted_raw_output],
    )

    app.load(
        fn=refresh_tasks,
        inputs=[current_page_state, page_size_selector],
        outputs=[task_table, task_selector, home_status, current_page_state, page_info],
    )
    app.load(
        fn=refresh_inserted_data,
        inputs=[inserted_current_page_state, inserted_page_size_selector],
        outputs=[inserted_data_table, inserted_status, inserted_current_page_state, inserted_page_info, inserted_raw_output],
    )


if __name__ == "__main__":
    app.launch(server_name=SERVER_HOST, server_port=SERVER_PORT)