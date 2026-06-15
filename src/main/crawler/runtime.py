import asyncio
import datetime
import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from dateutil.tz import tzoffset
from lxml import etree
from loguru import logger

from src.utils.ai_tools import contains_chinese, match_web_url_class_label, translate_content, translate_title
from src.utils.playwright_manager import playwright_fetch, playwright_login_and_get_headers_sync
from src.utils.source_name_mapping import map_source_name_cn_by_url


XPathValue = Union[str, List[str]]


class ConfigurableXPathCrawler:
    """基于 XPath 配置执行列表页/详情页采集的轻量运行时。"""

    def __init__(self, task_config: Dict):
        self.task_config = task_config
        self.source_name: str = task_config["source_name"]
        self.prefix: str = task_config.get("prefix") or ""
        self.home_url_list: List[str] = task_config["home_url_list"]
        self.url_xpath: XPathValue = task_config["url_xpath"]
        self.title_xpath: XPathValue = task_config["title_xpath"]
        self.content_xpath: XPathValue = task_config["content_xpath"]
        self.home_date_xpath: XPathValue = task_config.get("home_date_xpath") or []
        self.date_xpath: XPathValue = task_config.get("date_xpath") or []
        self.image_xpath: XPathValue = task_config.get("image_xpath") or []
        self.detail_image_xpath: XPathValue = task_config.get("detail_image_xpath") or []
        self.url_limit: int = task_config.get("url_limit", 10)
        self.list_retry_count: int = task_config.get("list_retry_count", 1)
        self.list_retry_sleep_seconds: int = task_config.get("list_retry_sleep_seconds", 3)
        self.detail_retry_count: int = task_config.get("detail_retry_count", 0)
        self.detail_retry_sleep_seconds: int = task_config.get("detail_retry_sleep_seconds", 2)
        self.min_content_length: int = max(0, int(task_config.get("min_content_length", 0) or 0))
        self.max_content_length: int = max(0, int(task_config.get("max_content_length", 0) or 0))
        if self.max_content_length > 0 and self.max_content_length < self.min_content_length:
            logger.warning(
                "crawler长度配置异常: source={}, min_content_length={}, max_content_length={}, 已将 max_content_length 对齐为 min_content_length",
                self.source_name,
                self.min_content_length,
                self.max_content_length,
            )
            self.max_content_length = self.min_content_length
        self.dedupe_urls: bool = task_config.get("dedupe_urls", False)
        self.home_wait_xpath: XPathValue = task_config.get("home_wait_xpath") or []
        self.detail_wait_xpath: XPathValue = task_config.get("detail_wait_xpath") or []
        self.source_language: str = task_config.get("source_language") or "auto"
        self.source_map: Dict[str, str] = task_config.get("source_map") or {}
        self.content_joiner: str = task_config.get("content_joiner") or "\n"
        self.default_image_url: str = task_config.get("default_image_url") or (
            "https://ai-doc.data.myvessel.cn/news/%E8%88%AA%E8%BF%90%E5%BF%AB%E8%AE%AF%E5%A4%B4"
            "%E5%9B%BE.jpg?OSSAccessKeyId=LTAI5t7nfdMfD7YeTFpAENJ4&Expires=2725518616&"
            "Signature=Tw08oPC0RL%2FKweHU1Q1NlJZhZHA%3D"
        )
        self.date_patterns: List[str] = task_config.get("date_patterns") or [
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
        ]
        
        # 登录相关配置
        self.login_enabled: bool = task_config.get("login_enabled", False)
        self.login_username: str = task_config.get("login_username") or ""
        self.login_password: str = task_config.get("login_password") or ""
        self.playwright_login_url: str = task_config.get("playwright_login_url") or ""
        self.playwright_login_entry_xpath: str = task_config.get("playwright_login_entry_xpath") or ""
        self.playwright_login_username_xpath: str = task_config.get("playwright_login_username_xpath") or ""
        self.playwright_login_password_xpath: str = task_config.get("playwright_login_password_xpath") or ""
        self.playwright_login_submit_xpath: str = task_config.get("playwright_login_submit_xpath") or ""
        self.playwright_login_success_xpath: str = task_config.get("playwright_login_success_xpath") or ""
        self.playwright_login_timeout: int = task_config.get("playwright_login_timeout", 60)
        self.playwright_headless: bool = task_config.get("playwright_headless", True)
        
        # 正文图片占位配置
        self.enable_content_image_placeholder: bool = task_config.get("enable_content_image_placeholder", False)
        self.content_root_xpath: XPathValue = task_config.get("content_root_xpath") or []
        self.content_image_xpath: XPathValue = task_config.get("content_image_xpath") or []
        self.content_image_placeholder_template: str = task_config.get("content_image_placeholder_template") or "![图片{index}]({url})"
        self.append_content_image_mapping: bool = task_config.get("append_content_image_mapping", False)
        
        # 登录状态缓存
        self._login_headers_cache: Dict[str, Dict[str, str]] = {}

        # 动态绑定自定义方法重写
        self._bind_custom_methods(task_config.get("custom_methods") or {})

    def _bind_custom_methods(self, custom_methods: Dict[str, str]) -> None:
        """编译并绑定用户定义的自定义方法到当前实例。

        动态编译的函数没有类继承上下文，因此 ``super()`` 无法工作。
        这里在编译命名空间中注入 ``_super`` 代理，指向实例上绑定前的原始方法，
        用户代码中应使用 ``_super.method_name(...)`` 代替 ``super().method_name(...)``。
        同时也会将 ``super`` 本身替换为一个兼容的代理函数。
        """
        if not custom_methods:
            return

        from src.utils.template_parser import compile_custom_methods

        # 在绑定前，先收集原始方法引用，供 super() 代理使用
        original_methods: Dict[str, Any] = {}
        for method_name in custom_methods:
            orig = getattr(self, method_name, None)
            if orig is not None:
                original_methods[method_name] = orig

        # 构建 super() 代理：调用 _super.method_name(...) 等价于 super().method_name(...)
        class _SuperProxy:
            def __getattr__(self, name: str):
                if name in original_methods:
                    return original_methods[name]
                raise AttributeError(f"原始方法 {name!r} 不存在，无法通过 _super 调用")

        try:
            compiled = compile_custom_methods(custom_methods, extra_namespace={
                "_super": _SuperProxy(),
            })
        except ValueError as e:
            logger.error(f"自定义方法编译失败，已跳过: source={self.source_name}, error={e}")
            return

        import types
        for method_name, func in compiled.items():
            try:
                if isinstance(func, staticmethod):
                    # @staticmethod: 剥离装饰器，直接设为普通函数（不绑定 self）
                    underlying = func.__func__
                    setattr(self, method_name, underlying)
                    logger.info(f"已绑定静态方法: source={self.source_name}, method={method_name}")
                elif isinstance(func, classmethod):
                    # @classmethod: 提取底层函数，绑定 cls 为实例的类
                    underlying = func.__func__
                    bound = types.MethodType(underlying, type(self))
                    setattr(self, method_name, bound)
                    logger.info(f"已绑定类方法: source={self.source_name}, method={method_name}")
                else:
                    # 普通方法: 绑定为实例方法
                    bound = types.MethodType(func, self)
                    setattr(self, method_name, bound)
                    logger.info(f"已绑定自定义方法: source={self.source_name}, method={method_name}")
            except Exception as e:
                logger.error(f"绑定自定义方法失败: source={self.source_name}, method={method_name}, error={e}")

    # ── 登录流程 ──────────────────────────────────────────────

    def login_and_build_headers(self, home_url: str) -> Dict[str, str]:
        """执行 Playwright 模拟登录并返回可用请求头。"""
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
        """获取登录请求头（带缓存）。"""
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

    # ── 正文图片占位 ─────────────────────────────────────────

    @staticmethod
    def _derive_root_xpath_from_content_xpath(content_xpath: str) -> str:
        xpath = (content_xpath or "").strip()
        if not xpath:
            return ""
        xpath = re.sub(r"//text\(\).*$", "", xpath)
        xpath = re.sub(r"/text\(\).*$", "", xpath)
        return xpath.strip()

    def _serialize_content_with_images(self, detail_page, detail_url: str):
        """序列化正文节点，按 DOM 顺序交替提取文本和图片占位符。"""
        root_xpath_values = self.ensure_xpath_list(self.content_root_xpath)
        if not root_xpath_values:
            content_xpath_values = self.ensure_xpath_list(self.content_xpath)
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
                    normalized_src = self.normalize_url(raw_src)
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

        content = self.join_cleaned_paragraphs(parts)
        return content, image_mappings

    def build_content_text(self, detail_page, detail_url: str) -> str:
        """构建正文文本，启用图片占位时插入占位符与映射。"""
        if not self.enable_content_image_placeholder:
            detail_contents_list = self.extract_first_text_list(detail_page, self.content_xpath)
            return self.join_cleaned_paragraphs(detail_contents_list)

        detail_contents_raw, image_mappings = self._serialize_content_with_images(detail_page, detail_url)
        if not detail_contents_raw:
            detail_contents_list = self.extract_first_text_list(detail_page, self.content_xpath)
            detail_contents_raw = self.join_cleaned_paragraphs(detail_contents_list)

        if image_mappings and self.append_content_image_mapping:
            mapping_lines = [f"{item['placeholder']} => {item['image_url']}" for item in image_mappings]
            detail_contents_raw = f"{detail_contents_raw}\n\n图片映射:\n" + "\n".join(mapping_lines)
        return detail_contents_raw

    # ── 基础工具方法 ─────────────────────────────────────────

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        cleaned = text.replace("\xa0", " ").replace("\u200b", "").replace("\r", "")
        # 保留换行符，仅折叠空格和制表符
        cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
        # 去除每行首尾空格，合并连续空行
        lines = [line.strip() for line in cleaned.split("\n")]
        cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
        return cleaned.strip()

    @classmethod
    def join_cleaned_paragraphs(cls, paragraphs: List[str]) -> str:
        cleaned_paragraphs = [cls.clean_text(paragraph) for paragraph in paragraphs]
        return "\n".join(paragraph for paragraph in cleaned_paragraphs if paragraph)

    @staticmethod
    def ensure_xpath_list(xpath_value: Union[XPathValue, tuple, None]) -> List[str]:
        if not xpath_value:
            return []
        if isinstance(xpath_value, str):
            return [xpath_value]
        return [item for item in xpath_value if item]

    # ── XPath getter 方法（与基类 XPathCrawlerTaskBase 保持一致）──

    def get_date_xpath(self, home_url: str) -> XPathValue:
        return self.date_xpath

    def get_home_date_xpath(self, home_url: str) -> XPathValue:
        return self.home_date_xpath

    def get_url_xpath(self, home_url: str) -> XPathValue:
        return self.url_xpath

    def get_title_xpath(self, home_url: str) -> XPathValue:
        return self.title_xpath

    def get_content_xpath(self, home_url: str) -> XPathValue:
        return self.content_xpath

    def get_content_root_xpath(self, home_url: str) -> XPathValue:
        return self.content_root_xpath

    def get_content_image_xpath(self, home_url: str) -> XPathValue:
        return self.content_image_xpath

    def get_image_xpath(self, home_url: str) -> XPathValue:
        return self.image_xpath

    def get_detail_image_xpath(self, home_url: str) -> XPathValue:
        return self.detail_image_xpath

    def get_home_wait_xpath(self, home_url: str) -> XPathValue:
        return self.home_wait_xpath

    def get_detail_wait_xpath(self, home_url: str) -> XPathValue:
        return self.detail_wait_xpath

    def normalize_url(self, url: str, base_url: Optional[str] = None) -> str:
        if not url:
            return ""
        if url.startswith(("http://", "https://")):
            return url
        # 优先使用 base_url，其次使用 self.prefix
        prefix = base_url or self.prefix
        if not prefix:
            return url
        if prefix.endswith("/") and url.startswith("/"):
            return f"{prefix[:-1]}{url}"
        if not prefix.endswith("/") and not url.startswith("/"):
            return f"{prefix}/{url}"
        return f"{prefix}{url}"

    @staticmethod
    def extract_url_from_node(node) -> str:
        if hasattr(node, "get"):
            for attr in ("data-src", "data-original", "data-lazy-src", "src", "href"):
                value = (node.get(attr) or "").strip()
                if not value:
                    continue
                if attr == "src" and "placeholder.jpg" in value.lower():
                    continue
                return value
            return ""
        text_value = str(node).strip()
        return text_value

    def preprocess_date_text(self, time_str: str) -> str:
        raw_value = (time_str or "").strip()
        return re.sub(r"^(update|updated)\s*:\s*", "", raw_value, flags=re.IGNORECASE)

    def convert_date_format(self, time_str: str) -> tuple[str, str]:
        normalized = self.preprocess_date_text(time_str)
        parsed_dt: Optional[datetime.datetime] = None
        for pattern in self.date_patterns:
            try:
                parsed_dt = datetime.datetime.strptime(normalized, pattern)
                break
            except ValueError:
                continue

        # 兜底 ISO8601，例如 2026-03-16T18:43:45+05:30 或带 Z 后缀。
        if parsed_dt is None:
            iso_candidate = normalized.replace("Z", "+00:00")
            try:
                parsed_dt = datetime.datetime.fromisoformat(iso_candidate)
            except ValueError:
                parsed_dt = None

        if parsed_dt is None:
            logger.warning(f"无法解析日期格式: {normalized}，使用当前时间")
            parsed_dt = datetime.datetime.now()

        date_str = parsed_dt.strftime("%Y-%m-%d")
        if parsed_dt.tzinfo is None:
            dt_utc8 = parsed_dt.replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
        else:
            dt_utc8 = parsed_dt.astimezone(tzoffset("UTC+8", 8 * 3600))
        datetime_str = dt_utc8.strftime("%Y-%m-%d %H:%M:%S%z")
        return date_str, datetime_str

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
        for known_domain, source_name in self.source_map.items():
            normalized_known_domain = self.normalize_domain(known_domain)
            if domain == normalized_known_domain or domain.endswith(f".{normalized_known_domain}"):
                return source_name
        return ""

    def get_source_language(self, home_url: str, detail_title: str, detail_contents: str) -> str:
        configured_language = (self.source_language or "auto").strip().lower()
        if configured_language != "auto":
            return configured_language

        if contains_chinese(f"{detail_title}\n{detail_contents}"):
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

    def fetch_page(
        self,
        url: str,
        wait_xpath: Optional[XPathValue] = None,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[etree._Element]:
        result = asyncio.run(
            playwright_fetch(
                url,
                wait_xpath=wait_xpath,
                request_headers=request_headers,
                headless=self.playwright_headless,
            )
        )
        if not result or not result.get("status") or not result.get("html"):
            return None
        return etree.HTML(result["html"])

    def fetch_home_page(self, home_url: str):
        attempts = self.list_retry_count + 1
        login_headers = self.get_login_headers(home_url) if self.login_enabled else {}
        for attempt in range(attempts):
            parsed_page = self.fetch_page(
                home_url,
                wait_xpath=self.home_wait_xpath,
                request_headers=login_headers or None,
            )
            if parsed_page is not None:
                return parsed_page
            if attempt < attempts - 1:
                time.sleep(self.list_retry_sleep_seconds)
        logger.error(f"crawler首页抓取失败且已耗尽重试: source={self.source_name}, home_url={home_url}")
        return None

    def extract_first_text(self, page, xpath_value: XPathValue, field_name: str) -> str:
        for xpath in self.ensure_xpath_list(xpath_value):
            try:
                nodes = page.xpath(xpath)
            except etree.XPathError as exc:
                logger.warning(
                    f"{field_name} XPath 非法，已跳过: source={self.source_name}, xpath={xpath}, error={exc}"
                )
                continue
            for node in nodes:
                text = self.clean_text(str(node))
                if text:
                    return text
        raise ValueError(f"{field_name} 节点为空")

    def extract_first_url_list(self, page, xpath_value: XPathValue) -> List[str]:
        for xpath in self.ensure_xpath_list(xpath_value):
            try:
                nodes = page.xpath(xpath)
            except etree.XPathError as exc:
                logger.warning(
                    f"URL XPath 非法，已跳过: source={self.source_name}, xpath={xpath}, error={exc}"
                )
                continue
            values = []
            for node in nodes:
                raw_url = self.extract_url_from_node(node)
                if not raw_url:
                    continue
                normalized_url = self.normalize_url(raw_url)
                if normalized_url:
                    values.append(normalized_url)
            if values:
                return values
        return []

    def extract_first_text_list(self, page, xpath_value: XPathValue) -> List[str]:
        for xpath in self.ensure_xpath_list(xpath_value):
            values = []
            try:
                nodes = page.xpath(xpath)
            except etree.XPathError as exc:
                logger.warning(
                    f"文本 XPath 非法，已跳过: source={self.source_name}, xpath={xpath}, error={exc}"
                )
                continue
            for node in nodes:
                text = self.clean_text(str(node))
                if text:
                    values.append(text)
            if values:
                return values
        return []

    def extract_first_image_url(self, page, image_xpath: XPathValue) -> Optional[str]:
        image_nodes = self.extract_first_url_list(page, image_xpath)
        return image_nodes[0] if image_nodes else None

    def resolve_image_url(self, home_url: str, detail_page, item: dict) -> str:
        list_image_url = item.get("img_url")
        if list_image_url:
            return list_image_url
        detail_image_url = self.extract_first_image_url(detail_page, self.detail_image_xpath)
        if detail_image_url:
            return detail_image_url
        return self.default_image_url

    def extract_list_items(self, home_url: str, parsed_page) -> list:
        raw_urls = self.extract_first_url_list(parsed_page, self.url_xpath)
        if self.dedupe_urls:
            raw_urls = list(dict.fromkeys(raw_urls))
        detail_urls = raw_urls[: self.url_limit]

        img_urls = self.extract_first_url_list(parsed_page, self.image_xpath)[: self.url_limit] if self.image_xpath else []
        home_dates = self.extract_first_text_list(parsed_page, self.home_date_xpath)[: self.url_limit] if self.home_date_xpath else []

        logger.info(
            f"crawler列表页提取统计: source={self.source_name}, detail_url_count={len(detail_urls)}, "
            f"img_count={len(img_urls)}, home_date_count={len(home_dates)}, "
            f"has_image_xpath={bool(self.image_xpath)}, has_home_date_xpath={bool(self.home_date_xpath)}"
        )

        if detail_urls and self.image_xpath and not img_urls:
            error_msg = (
                f"crawler列表图片为空: source={self.source_name}, image_xpath={self.image_xpath}, "
                "已抓到详情链接但图片提取为空，任务按失败处理"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        if detail_urls and self.home_date_xpath and not home_dates:
            error_msg = (
                f"crawler列表日期为空: source={self.source_name}, home_date_xpath={self.home_date_xpath}, "
                "已抓到详情链接但日期提取为空，任务按失败处理"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        if self.image_xpath and self.home_date_xpath:
            items = [
                {"detail_url": detail_url, "img_url": img_url, "detail_date": home_date}
                for detail_url, img_url, home_date in zip(detail_urls, img_urls, home_dates)
            ]
            if detail_urls and not items:
                logger.warning(
                    f"crawler列表项为空: source={self.source_name}, reason=zip(detail_urls,img_urls,home_dates)被截断"
                )
            return items
        if self.image_xpath:
            items = [
                {"detail_url": detail_url, "img_url": img_url, "detail_date": None}
                for detail_url, img_url in zip(detail_urls, img_urls)
            ]
            if detail_urls and not items:
                logger.warning(
                    f"crawler列表项为空: source={self.source_name}, reason=zip(detail_urls,img_urls)被截断"
                )
            return items
        if self.home_date_xpath:
            items = [
                {"detail_url": detail_url, "img_url": None, "detail_date": home_date}
                for detail_url, home_date in zip(detail_urls, home_dates)
            ]
            if detail_urls and not items:
                logger.warning(
                    f"crawler列表项为空: source={self.source_name}, reason=zip(detail_urls,home_dates)被截断"
                )
            return items
        return [{"detail_url": detail_url, "img_url": None, "detail_date": None} for detail_url in detail_urls]

    def build_language_fields(self, home_url: str, detail_title: str, detail_contents: str) -> Dict[str, str]:
        source_language = self.get_source_language(home_url, detail_title, detail_contents)

        if self.is_chinese_language(source_language):
            return {
                "detail_title_cn": detail_title,
                "detail_contents_cn": detail_contents,
            }

        if self.should_translate_to_english(source_language):
            return {
                "detail_title": translate_title(
                    detail_title,
                    target_language="en",
                    source_language=source_language,
                ),
                "detail_contents": translate_content(
                    detail_contents,
                    target_language="en",
                    source_language=source_language,
                ),
            }

        return {
            "detail_title": detail_title,
            "detail_contents": detail_contents,
        }

    def build_article_id(self, result: dict) -> Optional[str]:
        detail_url = (result.get("detail_url") or "").strip()
        detail_date = (result.get("detail_date") or "").split(" ")[0].replace("-", "")
        if detail_url and detail_date:
            try:
                parsed = urlparse(detail_url)
                normalized_path = parsed.path.rstrip("/") or "/"
                normalized_url = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{normalized_path}"
                url_digest = hashlib.md5(normalized_url.encode("utf-8")).hexdigest()[:12]
                return f"{self.source_name}_{detail_date}_{url_digest}"
            except Exception as exc:
                logger.warning(f"article_id URL哈希生成失败，回退标题方案: source={self.source_name}, error={exc}")

        try:
            primary_key = (
                self.source_name
                + "_"
                + result.get("detail_date").split(" ")[0].replace("-", "")
                + "_"
                + result.get("detail_title")[:4]
                + result.get("detail_title")[-4:]
            )
            return primary_key
        except Exception:
            try:
                primary_key = (
                    self.source_name
                    + "_"
                    + result.get("detail_date").split(" ")[0].replace("-", "")
                    + "_"
                    + result.get("detail_title_cn")[:4]
                    + result.get("detail_title_cn")[-4:]
                )
                return primary_key
            except Exception as exc:
                logger.error(exc)
                return None

    def build_res_record(self, home_url: str, detail_page, item: dict) -> dict:
        detail_url = item["detail_url"]
        detail_title_raw = self.extract_first_text(detail_page, self.title_xpath, "标题")
        detail_contents_raw = self.build_content_text(detail_page, detail_url)
        date_text = item.get("detail_date") or self.extract_first_text(detail_page, self.date_xpath, "日期")
        date_str, datetime_str = self.convert_date_format(date_text)

        result = {
            "detail_url": detail_url,
            "detail_date": date_str,
            "detail_timestamptz": datetime_str,
            "img_parse_url": self.resolve_image_url(home_url, detail_page, item),
        }
        result.update(self.build_language_fields(home_url, detail_title_raw, detail_contents_raw))
        detail_title = result.get("detail_title") or ""
        detail_contents = result.get("detail_contents") or ""
        detail_title_cn = result.get("detail_title_cn") or ""
        detail_contents_cn = result.get("detail_contents_cn") or ""
        class_title = detail_title or detail_title_cn or detail_title_raw
        class_contents = detail_contents or detail_contents_cn or detail_contents_raw
        result.update(
            {
                "article_id": self.build_article_id(result),
                "class_level_1": match_web_url_class_label(class_title, class_contents),
                "class_level_2": "",
                "keyword1": None,
                "keyword2": None,
                "keyword3": None,
                "is_translated": "no",
                "abstract": None,
                "abstract_cn": None,
                "obs_url": None,
            }
        )
        news_source_name_cn = self.get_news_source_name_cn(detail_url) or map_source_name_cn_by_url(detail_url)
        if news_source_name_cn:
            result["news_source_name_cn"] = news_source_name_cn
        if not detail_title and not detail_title_cn:
            result["detail_title"] = detail_title_raw
        if not detail_contents and not detail_contents_cn:
            result["detail_contents"] = detail_contents_raw
        return result

    def process_detail_item(self, home_url: str, item: Dict[str, Optional[str]]) -> Optional[dict]:
        detail_url = item["detail_url"]
        attempts = self.detail_retry_count + 1
        login_headers = self.get_login_headers(home_url) if self.login_enabled else {}
        for attempt in range(attempts):
            try:
                detail_page = self.fetch_page(
                    detail_url,
                    wait_xpath=self.detail_wait_xpath,
                    request_headers=login_headers or None,
                )
                if detail_page is None:
                    raise ValueError("详情页解析失败")
                result = self.build_res_record(home_url, detail_page, item)
                logger.info(
                    f"crawler详情页处理成功: source={self.source_name}, detail_url={detail_url}, attempt={attempt + 1}, article_id={result.get('article_id')}"
                )
                return result
            except Exception as exc:
                if attempt < attempts - 1:
                    logger.warning(f"详情解析失败，准备重试: {detail_url}, error: {exc}")
                    time.sleep(self.detail_retry_sleep_seconds)
                else:
                    logger.error(f"详情解析失败: {detail_url}, error: {exc}")
        return None

    def run(self) -> List[Dict]:
        records: List[Dict] = []
        home_page_failed_count = 0
        list_item_total = 0
        detail_failed_count = 0
        empty_content_skipped_count = 0
        min_content_skipped_count = 0
        max_content_skipped_count = 0
        logger.info(
            f"crawler运行开始: source={self.source_name}, home_url_count={len(self.home_url_list)}, "
            f"url_limit={self.url_limit}, min_content_length={self.min_content_length}, "
            f"max_content_length={self.max_content_length}"
        )
        for home_url in self.home_url_list:
            parsed_page = self.fetch_home_page(home_url)
            if parsed_page is None:
                logger.error(f"主页解析失败: {home_url}")
                home_page_failed_count += 1
                continue
            items = self.extract_list_items(home_url, parsed_page)
            list_item_total += len(items)
            logger.info(
                f"crawler首页处理: source={self.source_name}, home_url={home_url}, list_item_count={len(items)}"
            )
            for item in items:
                result = self.process_detail_item(home_url, item)
                if not result:
                    detail_failed_count += 1
                    continue
                detail_contents = self.clean_text(result.get("detail_contents") or "")
                detail_contents_cn = self.clean_text(result.get("detail_contents_cn") or "")
                content_length = max(len(detail_contents), len(detail_contents_cn))

                if content_length <= 0:
                    logger.warning(
                        f"crawler详情页正文为空，跳过: source={self.source_name}, article_id={result.get('article_id')}, detail_url={result.get('detail_url')}"
                    )
                    empty_content_skipped_count += 1
                    continue
                if self.min_content_length > 0 and content_length < self.min_content_length:
                    logger.warning(
                        f"crawler详情页正文长度不足，跳过: source={self.source_name}, article_id={result.get('article_id')}, "
                        f"detail_url={result.get('detail_url')}, content_length={content_length}, "
                        f"min_content_length={self.min_content_length}"
                    )
                    min_content_skipped_count += 1
                    continue
                if self.max_content_length > 0 and content_length > self.max_content_length:
                    logger.warning(
                        f"crawler详情页正文长度超限，跳过: source={self.source_name}, article_id={result.get('article_id')}, "
                        f"detail_url={result.get('detail_url')}, content_length={content_length}, "
                        f"max_content_length={self.max_content_length}"
                    )
                    max_content_skipped_count += 1
                    continue
                records.append(result)

        if not records:
            error_msg = (
                f"crawler无有效结果: source={self.source_name}, home_url_count={len(self.home_url_list)}, "
                f"home_page_failed_count={home_page_failed_count}, list_item_total={list_item_total}, "
                f"detail_failed_count={detail_failed_count}, empty_content_skipped_count={empty_content_skipped_count}, "
                f"min_content_skipped_count={min_content_skipped_count}, min_content_length={self.min_content_length}, "
                f"max_content_skipped_count={max_content_skipped_count}, max_content_length={self.max_content_length}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"crawler运行结束: source={self.source_name}, total_records={len(records)}")
        return records