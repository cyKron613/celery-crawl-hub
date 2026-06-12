import datetime
import posixpath
import random
import re
import time
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

import pandas as pd
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from dateutil.tz import tzoffset
from loguru import logger

from src.utils.ai_tools import match_web_url_class_label, translate_content, translate_title
from src.utils.craw_tools import fetch_and_parse, get_primary_key, insert_into_table
from src.utils.playwright_manager import playwright_login_and_get_headers_sync


XPathValue = Union[str, List[str]]


class XPathCrawlerTaskBase:
    """
    :param source_name: 数据来源名称，作为数据表的主键前缀 article_id基于此生成
    :param prefix: URL前缀，方便构建完整URL"
    :param home_url_list: 主页URL列表，爬虫将从这些URL开始爬取数据
    :param url_xpath: 列表页URL的XPath表达式
    :param title_xpath: 详情页标题的XPath表达式
    :param content_xpath: 详情页内容的XPath表达式
    :param home_date_xpath: 列表页日期的XPath表达式，存在时会与详情URL按顺序配对
    :param date_xpath: 详情页日期的XPath表达式
    :param image_xpath: 列表页图片URL的XPath表达式，存在时会与详情URL按顺序zip配对
    :param detail_image_xpath: 详情页图片URL的XPath表达式，不存在列表图时在详情页单独提取
    :param url_limit: 每个主页URL要爬取的详情页URL数量
    :param list_retry_count: 列表页重试次数
    :param list_retry_sleep_seconds: 列表页重试间隔秒数
    :param detail_retry_count: 详情页重试次数
    :param detail_retry_sleep_seconds: 详情页重试间隔秒数
    :param home_request_delay_seconds: 首页请求前固定等待秒数
    :param home_request_delay_jitter_seconds: 首页请求前随机抖动秒数
    :param detail_request_delay_seconds: 详情页请求前固定等待秒数
    :param detail_request_delay_jitter_seconds: 详情页请求前随机抖动秒数
    :param dedupe_urls: 是否去重URL
    :param home_wait_xpath: 首页等待渲染完成时使用的 xpath 配置
    :param detail_wait_xpath: 详情页等待渲染完成时使用的 xpath 配置
    :param fetch_timeout: 抓取超时时间，传给 fetch_and_parse
    :param content_joiner: 内容拼接符
    :param default_image_url: 默认图片URL，航运头图
    :param date_patterns: 日期格式列表
    :param min_content_length: 最小正文长度，小于该值时过滤
    :param max_content_length: 最大正文长度，大于该值时过滤，0 表示不限制
    :param login_enabled: 是否启用 Playwright 登录态请求
    :param playwright_headless: Playwright 是否使用无头模式，默认跟随全局配置
    :param source_language: 来源语言，默认 auto
    """

    source_name: str = ""
    prefix: str = ""
    home_url_list: List[str] = []

    url_xpath: XPathValue = ""
    title_xpath: XPathValue = ""
    content_xpath: XPathValue = ""
    home_date_xpath: XPathValue = ""
    date_xpath: XPathValue = ""
    image_xpath: XPathValue = ""
    detail_image_xpath: XPathValue = ""

    url_limit: int = 10
    list_retry_count: int = 1
    list_retry_sleep_seconds: int = 3
    detail_retry_count: int = 0
    detail_retry_sleep_seconds: int = 2
    home_request_delay_seconds: float = 0
    home_request_delay_jitter_seconds: float = 0
    detail_request_delay_seconds: float = 0
    detail_request_delay_jitter_seconds: float = 0
    dedupe_urls: bool = False
    home_wait_xpath: XPathValue = ""
    detail_wait_xpath: XPathValue = ""
    fetch_timeout: int = 360
    min_content_length: int = 0
    max_content_length: int = 0
    login_enabled: bool = False
    login_username: str = ""
    login_password: str = ""
    playwright_login_url: str = ""
    playwright_login_entry_xpath: str = ""
    playwright_login_username_xpath: str = ""
    playwright_login_password_xpath: str = ""
    playwright_login_submit_xpath: str = ""
    playwright_login_success_xpath: str = ""
    playwright_login_timeout: int = 60
    playwright_headless: bool = True
    enable_content_image_placeholder: bool = False
    content_root_xpath: XPathValue = ""
    content_image_xpath: XPathValue = ".//img/@src"
    content_image_placeholder_template: str = "![图片{index}]({url})"
    append_content_image_mapping: bool = False
    source_language: str = "auto"
    source_map: Dict[str, str] = {}
    category: str = ""

    content_joiner: str = " "
    default_image_url: str = (
        "https://ai-doc.data.myvessel.cn/news/%E8%88%AA%E8%BF%90%E5%BF%AB%E8%AE%AF%E5%A4%B4"
        "%E5%9B%BE.jpg?OSSAccessKeyId=LTAI5t7nfdMfD7YeTFpAENJ4&Expires=2725518616&"
        "Signature=Tw08oPC0RL%2FKweHU1Q1NlJZhZHA%3D"
    )

    date_patterns: List[str] = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    def __init__(
        self,
        login_enabled: Optional[bool] = None,
        login_username: Optional[str] = None,
        login_password: Optional[str] = None,
        playwright_login_url: Optional[str] = None,
        playwright_login_entry_xpath: Optional[str] = None,
        playwright_login_username_xpath: Optional[str] = None,
        playwright_login_password_xpath: Optional[str] = None,
        playwright_login_submit_xpath: Optional[str] = None,
        playwright_login_success_xpath: Optional[str] = None,
        playwright_login_timeout: Optional[int] = None,
        playwright_headless: Optional[bool] = None,
        fetch_timeout: Optional[int] = None,
        category: Optional[str] = None,
    ):
        if login_enabled is not None:
            self.login_enabled = login_enabled
        if login_username is not None:
            self.login_username = login_username
        if login_password is not None:
            self.login_password = login_password
        if playwright_login_url is not None:
            self.playwright_login_url = playwright_login_url
        if playwright_login_entry_xpath is not None:
            self.playwright_login_entry_xpath = playwright_login_entry_xpath
        if playwright_login_username_xpath is not None:
            self.playwright_login_username_xpath = playwright_login_username_xpath
        if playwright_login_password_xpath is not None:
            self.playwright_login_password_xpath = playwright_login_password_xpath
        if playwright_login_submit_xpath is not None:
            self.playwright_login_submit_xpath = playwright_login_submit_xpath
        if playwright_login_success_xpath is not None:
            self.playwright_login_success_xpath = playwright_login_success_xpath
        if playwright_login_timeout is not None:
            self.playwright_login_timeout = playwright_login_timeout
        if playwright_headless is not None:
            self.playwright_headless = playwright_headless
        if fetch_timeout is not None:
            self.fetch_timeout = fetch_timeout
        if category is not None:
            self.category = category

        self._login_headers_cache: Dict[str, Dict[str, str]] = {}
        self.home_html: str = ""
        self.detail_html: str = ""

    @staticmethod
    def clean_text(text: str) -> str:
        """清洗文本中的多余空白和常见不可见字符。"""
        if not text:
            return ""
        cleaned = text.replace("\xa0", " ").replace("\u200b", " ").replace("\r", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def contains_chinese(text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", text or ""))

    def normalize_url(self, url: str, base_url: Optional[str] = None) -> str:
        """将相对链接转换为带前缀的完整链接。"""
        raw_url = (url or "").strip()
        if not raw_url:
            return ""

        def _normalize_url_path(full_url: str) -> str:
            parts = urlsplit(full_url)
            path = parts.path or "/"
            normalized_path = posixpath.normpath(path)
            if path.startswith("/") and not normalized_path.startswith("/"):
                normalized_path = f"/{normalized_path}"
            if path.endswith("/") and not normalized_path.endswith("/"):
                normalized_path = f"{normalized_path}/"
            return urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, parts.fragment))

        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            return _normalize_url_path(raw_url)

        join_base = (base_url or self.prefix or "").strip()
        if not join_base:
            return raw_url
        if not join_base.endswith("/"):
            join_base = f"{join_base}/"

        return _normalize_url_path(urljoin(join_base, raw_url))

    def preprocess_date_text(self, time_str: str) -> str:
        """预处理日期文本，移除固定前缀并做基础清洗。"""
        time_str = (time_str or "").strip()
        time_str = re.sub(r"^(update|updated)\s*:\s*", "", time_str, flags=re.IGNORECASE)
        time_str = re.sub(r"^(?:发布时间|发稿时间|发布日期|日期|时间)\s*[：:]\s*", "", time_str)
        time_str = re.sub(r",\s*by(?:\s+.*)?$", "", time_str, flags=re.IGNORECASE)
        time_str = re.sub(r"\s+(?:星期|周)[一二三四五六日天]$", "", time_str)

        datetime_patterns = [
            r"\b\d{4}-\d{1,2}-\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:\s?(?:Z|[+-]\d{2}:?\d{2}))?\b",
            r"\b\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?\b",
            r"\b\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}(?::\d{2})?\b",
        ]
        for pattern in datetime_patterns:
            match = re.search(pattern, time_str)
            if match:
                return match.group(0).strip()

        dash_date_match = re.search(r"\b\d{4}-\d{1,2}-\d{1,2}\b", time_str)
        if dash_date_match:
            return dash_date_match.group(0)

        slash_date_match = re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", time_str)
        if slash_date_match:
            return slash_date_match.group(0)

        return time_str.strip()

    def convert_date_format(self, time_str: str):
        """将原始日期文本转换为标准日期和带时区时间字符串。"""
        time_str = self.preprocess_date_text(time_str)
        parsed_dt = None

        for pattern in self.date_patterns:
            try:
                parsed_dt = datetime.datetime.strptime(time_str, pattern)
                break
            except ValueError:
                continue

        if parsed_dt is None:
            iso_candidate = time_str.replace("Z", "+00:00")
            try:
                parsed_dt = datetime.datetime.fromisoformat(iso_candidate)
            except ValueError:
                parsed_dt = None

        if parsed_dt is None:
            logger.warning(f"无法解析日期格式: {time_str}，使用当前日期")
            parsed_dt = datetime.datetime.now()

        date_str = parsed_dt.strftime("%Y-%m-%d")
        if parsed_dt.tzinfo is None:
            dt_utc8 = parsed_dt.replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
        else:
            dt_utc8 = parsed_dt.astimezone(tzoffset("UTC+8", 8 * 3600))
        datetime_str = dt_utc8.strftime("%Y-%m-%d %H:%M:%S%z")
        logger.info(f"日期转换: {time_str} -> {date_str}, {datetime_str}")
        return date_str, datetime_str

    @staticmethod
    def ensure_xpath_list(xpath_value: Union[XPathValue, tuple, None]) -> List[str]:
        """统一将单个 xpath 或多个 xpath 转换为列表。"""
        if not xpath_value:
            return []
        if isinstance(xpath_value, str):
            return [xpath_value]
        return [xpath for xpath in xpath_value if xpath]

    def extract_first_text(self, page, xpath_value: XPathValue, field_name: str) -> str:
        """按顺序尝试 xpath，返回首个非空文本结果。"""
        for xpath in self.ensure_xpath_list(xpath_value):
            nodes = page.xpath(xpath)
            for node in nodes:
                text = self.clean_text(str(node))
                if text:
                    return text
        raise ValueError(f"{field_name}节点为空")

    def extract_first_url_list(self, page, xpath_value: XPathValue, base_url: Optional[str] = None) -> List[str]:
        """按顺序尝试 xpath，返回首个非空 URL 列表。"""
        for xpath in self.ensure_xpath_list(xpath_value):
            values = [
                self.normalize_url(str(node).strip(), base_url=base_url)
                for node in page.xpath(xpath)
                if str(node).strip()
            ]
            if values:
                return values
        return []

    def extract_first_text_list(self, page, xpath_value: XPathValue) -> List[str]:
        """按顺序尝试 xpath，返回首个非空文本列表。"""
        for xpath in self.ensure_xpath_list(xpath_value):
            values = []
            for node in page.xpath(xpath):
                text = self.clean_text(str(node))
                if text:
                    values.append(text)
            if values:
                return values
        return []

    # 方便用户重写：根据主页URL动态返回不同的xpath配置，默认实现是直接返回属性值

    def get_date_xpath(self, home_url: str) -> XPathValue:
        """返回当前首页对应的日期 xpath 配置。"""
        return self.date_xpath

    def get_home_date_xpath(self, home_url: str) -> XPathValue:
        """返回当前首页对应的列表页日期 xpath 配置。"""
        return self.home_date_xpath

    def get_url_xpath(self, home_url: str) -> XPathValue:
        """返回当前首页对应的详情链接 xpath 配置。"""
        return self.url_xpath

    def get_title_xpath(self, home_url: str) -> XPathValue:
        """返回当前首页对应的标题 xpath 配置。"""
        return self.title_xpath

    def get_content_xpath(self, home_url: str) -> XPathValue:
        """返回当前首页对应的正文 xpath 配置。"""
        return self.content_xpath

    def get_content_root_xpath(self, home_url: str) -> XPathValue:
        """返回用于正文有序序列化的根节点 xpath。"""
        return self.content_root_xpath

    def get_content_image_xpath(self, home_url: str) -> XPathValue:
        """返回正文中图片链接 xpath。"""
        return self.content_image_xpath

    def get_image_xpath(self, home_url: str) -> XPathValue:
        """返回当前首页对应的列表图片 xpath 配置。"""
        return self.image_xpath

    def get_detail_image_xpath(self, home_url: str) -> XPathValue:
        """返回当前首页对应的详情图片 xpath 配置。"""
        return self.detail_image_xpath

    def get_home_wait_xpath(self, home_url: str) -> XPathValue:
        """返回首页等待渲染完成时使用的 xpath 配置。"""
        return self.home_wait_xpath

    def get_detail_wait_xpath(self, home_url: str) -> XPathValue:
        """返回详情页等待渲染完成时使用的 xpath 配置。"""
        return self.detail_wait_xpath

    def login_and_build_headers(self, home_url: str) -> Dict[str, str]:
        if not self.login_enabled:
            return {}

        login_url = self.playwright_login_url or home_url
        required_xpaths = [
            self.playwright_login_username_xpath,
            self.playwright_login_password_xpath,
            self.playwright_login_submit_xpath,
        ]
        if not self.login_username or not self.login_password:
            logger.warning(f"登录已启用但未提供账号密码: {home_url}")
            return {}
        if not all(required_xpaths):
            logger.warning(f"登录已启用但缺少 Playwright 登录 XPath 配置: {home_url}")
            return {}

        result = playwright_login_and_get_headers_sync(
            login_url=login_url,
            username=self.login_username,
            password=self.login_password,
            username_xpath=self.playwright_login_username_xpath,
            password_xpath=self.playwright_login_password_xpath,
            submit_xpath=self.playwright_login_submit_xpath,
            login_entry_xpath=self.playwright_login_entry_xpath or None,
            success_wait_xpath=self.playwright_login_success_xpath or None,
            timeout=self.playwright_login_timeout,
            headless=self.playwright_headless,
        )
        if result.get("status"):
            return result.get("headers", {})

        logger.warning(f"Playwright 模拟登录未获取到可用请求头: {home_url}")
        return {}

    def get_login_headers(self, home_url: str) -> Dict[str, str]:
        if not self.login_enabled:
            return {}
        if home_url in self._login_headers_cache:
            return self._login_headers_cache[home_url]

        headers = self.login_and_build_headers(home_url) or {}
        if headers:
            self._login_headers_cache[home_url] = headers
            return headers

        logger.warning(f"登录已启用但未获取到登录请求头: {home_url}")
        return {}

    def get_home_request_headers(self, home_url: str) -> Dict[str, str]:
        """返回首页请求头，子类可覆盖。"""
        return {}

    def get_detail_request_headers(self, home_url: str, detail_url: str) -> Dict[str, str]:
        """返回详情页请求头，子类可覆盖。"""
        return {}

    def sleep_before_request(self, stage: str, target_url: str):
        """按阶段执行请求前的固定延迟和抖动。"""
        if stage == "home":
            base_delay = max(float(self.home_request_delay_seconds or 0), 0)
            jitter_delay = max(float(self.home_request_delay_jitter_seconds or 0), 0)
        else:
            base_delay = max(float(self.detail_request_delay_seconds or 0), 0)
            jitter_delay = max(float(self.detail_request_delay_jitter_seconds or 0), 0)

        sleep_seconds = base_delay + (random.uniform(0, jitter_delay) if jitter_delay else 0)
        if sleep_seconds <= 0:
            return

        logger.info(
            f"{stage} 请求前等待 {sleep_seconds:.2f} 秒: {target_url} "
            f"(base={base_delay:.2f}, jitter={jitter_delay:.2f})"
        )
        time.sleep(sleep_seconds)

    def get_source_language(self, home_url: str, detail_title: str, detail_contents: str) -> str:
        configured_language = (self.source_language or "auto").strip().lower()
        if configured_language != "auto":
            return configured_language
        if self.contains_chinese(f"{detail_title}\n{detail_contents}"):
            return "zh"
        return "en"

    @staticmethod
    def is_chinese_language(language: str) -> bool:
        language_key = (language or "").strip().lower()
        return language_key.startswith("zh") or language_key in {"cn", "chinese", "中文"}

    @staticmethod
    def should_translate_to_english(language: str) -> bool:
        language_key = (language or "").strip().lower()
        return bool(language_key) and language_key not in {"auto", "en", "en-us", "en-gb"} and not language_key.startswith("zh")

    def build_language_fields(self, home_url: str, detail_title: str, detail_contents: str) -> Dict[str, str]:
        source_language = self.get_source_language(home_url, detail_title, detail_contents)

        if self.is_chinese_language(source_language):
            return {
                "detail_title_cn": detail_title,
                "detail_contents_cn": detail_contents,
            }

        if self.should_translate_to_english(source_language) and self.contains_chinese(f"{detail_title}\n{detail_contents}"):
            try:
                return {
                    "detail_title": translate_title(detail_title, "zh"),
                    "detail_contents": translate_content(detail_contents, "zh"),
                }
            except Exception as e:
                logger.warning(f"非英文内容翻译失败，回退原文: {e}")

        return {
            "detail_title": detail_title,
            "detail_contents": detail_contents,
        }

    @staticmethod
    def normalize_domain(url_or_domain: str) -> str:
        if not url_or_domain:
            return ""
        value = url_or_domain.strip().lower()
        if "://" not in value:
            value = f"https://{value}"
        parsed = urlparse(value)
        domain = parsed.netloc or parsed.path
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.split(":")[0]

    def get_news_source_name_cn(self, detail_url: str) -> str:
        domain = self.normalize_domain(detail_url)
        if not domain:
            return ""

        for known_domain, source_name in (self.source_map or {}).items():
            normalized_known_domain = self.normalize_domain(known_domain)
            if domain == normalized_known_domain or domain.endswith(f".{normalized_known_domain}"):
                return source_name
        return ""

    def get_category(self, home_url: str = "", detail_url: str = "") -> str:
        return str(self.category or "").strip()

    def extract_first_image_url(self, page, image_xpath: XPathValue) -> Optional[str]:
        """提取首个可用图片链接。"""
        image_nodes = self.extract_first_url_list(page, image_xpath)
        return image_nodes[0] if image_nodes else None

    @staticmethod
    def _derive_root_xpath_from_content_xpath(content_xpath: str) -> str:
        xpath = (content_xpath or "").strip()
        if not xpath:
            return ""
        xpath = re.sub(r"//text\(\).*$", "", xpath)
        xpath = re.sub(r"/text\(\).*$", "", xpath)
        return xpath.strip()

    def _serialize_content_with_images(self, home_url: str, detail_page, detail_url: str):
        root_xpath_values = self.ensure_xpath_list(self.get_content_root_xpath(home_url))
        if not root_xpath_values:
            content_xpath_values = self.ensure_xpath_list(self.get_content_xpath(home_url))
            for xpath in content_xpath_values:
                derived = self._derive_root_xpath_from_content_xpath(xpath)
                if derived:
                    root_xpath_values.append(derived)

        root_nodes = []
        for xpath in root_xpath_values:
            nodes = detail_page.xpath(xpath)
            if nodes:
                root_nodes = nodes
                break

        if not root_nodes:
            return "", []

        parts: List[str] = []
        image_mappings: List[Dict[str, str]] = []
        for root in root_nodes:
            ordered_nodes = root.xpath(".//text() | .//img")
            for node in ordered_nodes:
                if hasattr(node, "tag"):
                    if str(node.tag).lower() != "img":
                        continue
                    raw_src = (
                        (node.get("src") or "").strip()
                        or (node.get("data-src") or "").strip()
                        or (node.get("data-original") or "").strip()
                    )
                    if not raw_src:
                        continue
                    normalized_src = self.normalize_url(raw_src, base_url=detail_url)
                    image_index = len(image_mappings) + 1
                    placeholder = self.content_image_placeholder_template.format(index=image_index, url=normalized_src)
                    image_mappings.append(
                        {
                            "placeholder": placeholder,
                            "image_url": normalized_src,
                        }
                    )
                    parts.append(placeholder)
                    continue

                parent = getattr(node, "getparent", lambda: None)()
                if parent is not None and str(getattr(parent, "tag", "")).lower() in {"script", "style"}:
                    continue
                text = self.clean_text(str(node))
                if text:
                    parts.append(text)

        content = self.clean_text(self.content_joiner.join(parts))
        return content, image_mappings

    def build_content_text(self, home_url: str, detail_page, detail_url: str):
        """构建正文文本，并在启用时插入图片占位符与映射。"""
        if not self.enable_content_image_placeholder:
            detail_contents_list = self.extract_first_text_list(detail_page, self.get_content_xpath(home_url))
            return self.clean_text(self.content_joiner.join(detail_contents_list))

        detail_contents_raw, image_mappings = self._serialize_content_with_images(home_url, detail_page, detail_url)
        if not detail_contents_raw:
            detail_contents_list = self.extract_first_text_list(detail_page, self.get_content_xpath(home_url))
            detail_contents_raw = self.clean_text(self.content_joiner.join(detail_contents_list))

        if image_mappings and self.append_content_image_mapping:
            mapping_lines = [f"{item['placeholder']} => {item['image_url']}" for item in image_mappings]
            detail_contents_raw = f"{detail_contents_raw}\n\n图片映射:\n" + "\n".join(mapping_lines)
        return detail_contents_raw

    def resolve_image_url(self, home_url: str, detail_page, item: dict) -> str:
        """优先使用列表页图片，不存在时回退到详情页图片或默认图。"""
        list_image_url = item.get("img_url")

        if list_image_url:
            return list_image_url

        detail_image_url = self.extract_first_image_url(detail_page, self.get_detail_image_xpath(home_url))
        if detail_image_url:
            return detail_image_url

        return self.default_image_url

    def extract_list_items(self, home_url: str, parsed_page) -> list:
        """从列表页提取详情链接和可选的配套图片链接。"""
        raw_urls = self.extract_first_url_list(parsed_page, self.get_url_xpath(home_url), base_url=home_url)
        if self.dedupe_urls:
            raw_urls = list(dict.fromkeys(raw_urls))
        detail_urls = raw_urls[: self.url_limit]

        img_xpath = self.get_image_xpath(home_url)
        home_date_xpath = self.get_home_date_xpath(home_url)
        img_urls = self.extract_first_url_list(parsed_page, img_xpath, base_url=home_url)[: self.url_limit] if img_xpath else []
        home_dates = self.extract_first_text_list(parsed_page, home_date_xpath)[: self.url_limit] if home_date_xpath else []

        return [
            {
                "detail_url": detail_url,
                "img_url": img_urls[index] if index < len(img_urls) else None,
                "detail_date": home_dates[index] if index < len(home_dates) else None,
            }
            for index, detail_url in enumerate(detail_urls)
        ]

    def fetch_home_page(self, home_url: str):
        """抓取首页并按配置进行有限次重试。"""
        attempts = self.list_retry_count + 1
        for attempt in range(1, attempts + 1):
            try:
                self.sleep_before_request("home", home_url)
                request_headers = {}
                request_headers.update(self.get_login_headers(home_url))
                request_headers.update(self.get_home_request_headers(home_url))
                parsed_page = fetch_and_parse(
                    home_url,
                    timeout=self.fetch_timeout,
                    max_retries=1,
                    wait_xpath=self.get_home_wait_xpath(home_url),
                    request_headers=request_headers,
                    playwright_headless=self.playwright_headless,
                )
                self.home_html = parsed_page.get("html", "") if parsed_page else ""
                parsed_html = parsed_page.get("parse_html") if parsed_page else None
                if parsed_html is None:
                    raise ValueError("主页解析结果为空")
                return parsed_html
            except Exception as e:
                if attempt < attempts:
                    logger.warning(
                        f"{home_url} 第{attempt}/{attempts}次抓取失败: {e}; "
                        f"{self.list_retry_sleep_seconds}秒后重试"
                    )
                    time.sleep(self.list_retry_sleep_seconds)
                else:
                    logger.error(f"{home_url} 抓取失败，已达最大重试次数({attempts}): {e}")
        return None

    def build_res_record(self, home_url: str, detail_page, item: dict):
        """从详情页构建统一的入库结果字典。"""
        detail_url = item["detail_url"]
        detail_title_raw = self.extract_first_text(detail_page, self.get_title_xpath(home_url), "标题")
        detail_contents_raw = self.build_content_text(home_url, detail_page, detail_url)

        date_text = item.get("detail_date") or self.extract_first_text(detail_page, self.get_date_xpath(home_url), "日期")
        date_str, datetime_str = self.convert_date_format(date_text)

        img_parse_url = self.resolve_image_url(home_url, detail_page, item)

        res = {
            "img_parse_url": img_parse_url,
            "detail_url": detail_url,
            "detail_date": date_str,
            "detail_timestamptz": datetime_str,
        }
        res.update(self.build_language_fields(home_url, detail_title_raw, detail_contents_raw))

        news_source_name_cn = self.get_news_source_name_cn(detail_url)
        if news_source_name_cn:
            res["news_source_name_cn"] = news_source_name_cn

        article_id = get_primary_key(self.source_name, res)
        res["article_id"] = article_id
        dt_utc8 = datetime.datetime.now().replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
        res["update_time"] = dt_utc8.isoformat()
        class_title = res.get("detail_title") or res.get("detail_title_cn") or detail_title_raw
        class_contents = res.get("detail_contents") or res.get("detail_contents_cn") or detail_contents_raw
        res["class_level_1"] = match_web_url_class_label(class_title, class_contents)
        res["class_level_2"] = ""
        return res

    def process_detail_item(self, home_url: str, item: Dict[str, Optional[str]]):
        """抓取并解析单篇详情，失败时按配置重试。"""
        detail_url = item["detail_url"]
        attempts = self.detail_retry_count + 1
        for attempt in range(1, attempts + 1):
            try:
                self.sleep_before_request("detail", detail_url)
                request_headers = {}
                request_headers.update(self.get_login_headers(home_url))
                request_headers.update(self.get_detail_request_headers(home_url, detail_url))
                detail_parsed = fetch_and_parse(
                    detail_url,
                    timeout=self.fetch_timeout,
                    max_retries=1,
                    wait_xpath=self.get_detail_wait_xpath(home_url),
                    request_headers=request_headers,
                    playwright_headless=self.playwright_headless,
                )
                self.detail_html = detail_parsed.get("html", "") if detail_parsed else ""
                detail_page = detail_parsed.get("parse_html") if detail_parsed else None
                if detail_page is None:
                    raise ValueError("详情页解析结果为空")
                return self.build_res_record(home_url, detail_page, item)
            except Exception as e:
                if attempt < attempts:
                    logger.warning(
                        f"详情抓取失败({attempt}/{attempts}): {detail_url}, error: {e}; "
                        f"{self.detail_retry_sleep_seconds}秒后重试"
                    )
                    time.sleep(self.detail_retry_sleep_seconds)
                else:
                    logger.error(f"详情抓取失败，已达最大重试次数({attempts}): {detail_url}, error: {e}")
        return None

    @staticmethod
    def _insert_and_return(res_list: List[Dict]):
        """将结果列表批量写入数据库并返回字典列表。"""
        if not res_list:
            return []
        df = pd.DataFrame(res_list)
        df_dicts = df.to_dict(orient="records")
        insert_into_table(df_dicts)
        return df_dicts

    def run(self):
        """执行完整的首页到详情页抓取流程。"""
        res_list: List[Dict] = []
        try:
            for home_url in self.home_url_list:
                parsed_page = self.fetch_home_page(home_url)
                if parsed_page is None:
                    logger.error("主页解析失败!")
                    continue

                items = self.extract_list_items(home_url, parsed_page)
                if not items:
                    logger.warning(f"{home_url} 未获取到任何列表数据")
                    continue

                logger.info(f"解析获取了{len(items)}个对象")
                for item in items:
                    res = self.process_detail_item(home_url, item)
                    if not res:
                        continue
                    detail_contents = (res.get("detail_contents") or res.get("detail_contents_cn") or "").strip()
                    if not detail_contents:
                        logger.error(f"内容为空: {res.get('detail_url')}, {res.get('article_id')}")
                        continue
                    if self.min_content_length and len(detail_contents) < self.min_content_length:
                        logger.warning(
                            f"内容长度不足{self.min_content_length}: {res.get('detail_url')}, "
                            f"article_id={res.get('article_id')}, actual={len(detail_contents)}"
                        )
                        continue
                    if self.max_content_length and len(detail_contents) > self.max_content_length:
                        logger.warning(
                            f"内容长度超过{self.max_content_length}: {res.get('detail_url')}, "
                            f"article_id={res.get('article_id')}, actual={len(detail_contents)}"
                        )
                        continue
                    res_list.append(res)
                    logger.info(f"res: {res}")

            if res_list:
                return self._insert_and_return(res_list)

            logger.warning("未获取到任何有效数据")
            return []

        except SoftTimeLimitExceeded:
            logger.warning("任务执行时间超过软时间限制")
            if res_list:
                logger.info(f"当前软超时详情页数据条数: {len(res_list)}")
                self._insert_and_return(res_list)
            raise
        except TimeLimitExceeded:
            logger.error("任务执行时间超过硬时间限制")
            raise
        except Exception as e:
            logger.error(f"错误行: {e.__traceback__.tb_lineno}, error: {e}")
            if res_list:
                logger.info(f"当前详情页数据条数: {len(res_list)}")
                self._insert_and_return(res_list)
            raise


"""
FOR EXAMPLES

@@ -0,0 +1,35 @@

import pathlib
import sys
from celery import shared_task

ROOT_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent.parent.parent.parent.resolve()
sys.path.append(str(ROOT_DIR))

from src.utils.xpath_crawler_base import XPathCrawlerTaskBase
from src.utils.craw_tools import task_logging_decorator

class SCOCrawlerTask(XPathCrawlerTaskBase):
    source_name = "sco"
    prefix = "https://eng.sectsco.org"
    home_url_list = [
        'https://eng.sectsco.org/search/'
    ]
    url_xpath = '//article[@class="list-item"]/a/@href'
    date_xpath = "//time[@class='article-header__date']//text()"
    title_xpath = '//h1[@class="article-header__title"]//text()'
    content_xpath = "//div[@class='article-body__block article-body__block_text']//text()"
    image_xpath = "//fugure[@class='list-item__image']//img/@src"

    detail_wait_xpath = '//h1[@class="article-header__title"]'
    detail_retry_count = 1
    detail_retry_sleep_seconds = 2


@shared_task
@task_logging_decorator("sco", SCOCrawlerTask.home_url_list[0])
def time_task():
    crawler = SCOCrawlerTask()
    return crawler.run()

if __name__ == '__main__':
    time_task()


"""
