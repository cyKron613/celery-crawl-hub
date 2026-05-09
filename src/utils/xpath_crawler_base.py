import datetime
import re
import time
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse

import pandas as pd
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from dateutil.tz import tzoffset
from loguru import logger

from src.utils.ai_tools import contains_chinese, match_web_url_class_label, translate_content, translate_title
from src.utils.craw_tools import fetch_and_parse, get_primary_key, insert_into_table


XPathValue = Union[str, List[str]]


class XPathCrawlerTaskBase:
    """
    :param source_name: 数据来源名称，作为数据表的主键前缀 article_id基于此生成
    :param prefix: URL前缀，方便构建完整URL"
    :param home_url_list: 主页URL列表，爬虫将从这些URL开始爬取数据
    :param url_xpath: 列表页URL的XPath表达式
    :param title_xpath: 详情页标题的XPath表达式
    :param content_xpath: 详情页内容的XPath表达式
    :param home_date_xpath: 列表页日期的XPath表达式，存在时会与详情URL按顺序zip配对
    :param date_xpath: 详情页日期的XPath表达式
    :param image_xpath: 列表页图片URL的XPath表达式，存在时会与详情URL按顺序zip配对
    :param detail_image_xpath: 详情页图片URL的XPath表达式，不存在列表图时在详情页单独提取
    :param url_limit: 每个主页URL要爬取的详情页URL数量
    :param list_retry_count: 列表页重试次数
    :param list_retry_sleep_seconds: 列表页重试间隔秒数
    :param detail_retry_count: 详情页重试次数
    :param detail_retry_sleep_seconds: 详情页重试间隔秒数
    :param dedupe_urls: 是否去重URL
    :param content_joiner: 内容拼接符
    :param default_image_url: 默认图片URL，航运头图
    :param home_wait_xpath: 列表页等待渲染完成时使用的xpath配置，默认为空字符串表示不等待
    :param detail_wait_xpath: 详情页等待渲染完成时使用的xpath配置，默认为空字符串表示不等待
    :param source_language: 来源语言，默认为自动检测（auto），也可配置为特定语言如 "zh"、"en" 等
    :param source_map: 域名到新闻来源名称的映射，用于根据详情URL推断新闻来源名称
    :param date_patterns: 日期格式列表
    :param min_content_length: 最小内容长度，过滤掉内容过短的详情页
    :param max_content_length: 最大内容长度，过滤掉内容过长的详情页，0表示不限制
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
    min_content_length: int = 0
    max_content_length: int = 0
    dedupe_urls: bool = False
    home_wait_xpath: XPathValue = ""
    detail_wait_xpath: XPathValue = ""
    source_language: str = "auto"
    source_map: Dict[str, str] = {}

    content_joiner: str = " "
    default_image_url: str = (
        "https://ai-doc.data.myvessel.cn/news/%E8%88%AA%E8%BF%90%E5%BF%AB%E8%AE%AF%E5%A4%B4"
        "%E5%9B%BE.jpg?OSSAccessKeyId=LTAI5t7nfdMfD7YeTFpAENJ4&Expires=2725518616&"
        "Signature=Tw08oPC0RL%2FKweHU1Q1NlJZhZHA%3D"
    )

    date_patterns: List[str] = [
        "%d/%m/%y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%Y年%m月%d日",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    @staticmethod
    def clean_text(text: str) -> str:
        """清洗文本中的多余空白和常见不可见字符。"""
        # 简易清洗函数，去除多余空白和特殊字符
        if not text:
            return ""
        cleaned = text.replace("\xa0", " ").replace("\u200b", " ").replace("\r", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def normalize_url(self, url: str) -> str:
        """将相对链接转换为带前缀的完整链接。"""
        # url规范化，处理相对URL和绝对URL
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if not self.prefix:
            return url
        if self.prefix.endswith("/") and url.startswith("/"):
            return f"{self.prefix[:-1]}{url}"
        if not self.prefix.endswith("/") and not url.startswith("/"):
            return f"{self.prefix}/{url}"
        return f"{self.prefix}{url}"

    def preprocess_date_text(self, time_str: str) -> str:
        """预处理日期文本，移除固定前缀并做基础清洗。"""
        # 预处理日期文本，去除多余前缀和空白，待完善
        time_str = (time_str or "").strip()
        return re.sub(r"^(update|updated)\s*:\s*", "", time_str, flags=re.IGNORECASE)

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

        # 兜底处理 ISO8601，例如 2026-03-16T18:43:45+05:30 或带 Z 后缀。
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

    def extract_first_url_list(self, page, xpath_value: XPathValue) -> List[str]:
        """按顺序尝试 xpath，返回首个非空 URL 列表。"""
        for xpath in self.ensure_xpath_list(xpath_value):
            values = [self.normalize_url(str(node).strip()) for node in page.xpath(xpath) if str(node).strip()]
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

    def get_source_language(self, home_url: str, detail_title: str, detail_contents: str) -> str:
        """返回当前站点正文语言，默认自动判定中文，其余按配置值处理。"""
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

    def build_language_fields(self, home_url: str, detail_title: str, detail_contents: str) -> Dict[str, str]:
        """按源语言将标题和正文写入英文或中文字段。"""
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

    def extract_first_image_url(self, page, image_xpath: XPathValue) -> Optional[str]:
        """提取首个可用图片链接。"""
        image_nodes = self.extract_first_url_list(page, image_xpath)
        return image_nodes[0] if image_nodes else None

    def resolve_image_url(self, home_url: str, detail_page, item: dict) -> str:
        """优先使用列表页图片，不存在时回退到详情页图片或默认图。"""
        list_image_url = item.get("img_url")

        if list_image_url:
            return list_image_url

        detail_image_url = self.extract_first_image_url(detail_page, self.get_detail_image_xpath(home_url))
        if detail_image_url:
            return detail_image_url

        return self.default_image_url

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

    def extract_list_items(self, home_url: str, parsed_page) -> list:
        """从列表页提取详情链接和可选的配套图片链接。"""
        raw_urls = self.extract_first_url_list(parsed_page, self.get_url_xpath(home_url))
        if self.dedupe_urls:
            raw_urls = list(dict.fromkeys(raw_urls))
        detail_urls = raw_urls[: self.url_limit]

        img_xpath = self.get_image_xpath(home_url)
        home_date_xpath = self.get_home_date_xpath(home_url)
        img_urls = self.extract_first_url_list(parsed_page, img_xpath)[: self.url_limit] if img_xpath else []
        home_dates = self.extract_first_text_list(parsed_page, home_date_xpath)[: self.url_limit] if home_date_xpath else []

        if img_xpath and home_date_xpath:
            return [
                {"detail_url": detail_url, "img_url": img_url, "detail_date": home_date}
                for detail_url, img_url, home_date in zip(detail_urls, img_urls, home_dates)
            ]

        if img_xpath:
            return [
                {"detail_url": detail_url, "img_url": img_url, "detail_date": None}
                for detail_url, img_url in zip(detail_urls, img_urls)
            ]

        if home_date_xpath:
            return [
                {"detail_url": detail_url, "img_url": None, "detail_date": home_date}
                for detail_url, home_date in zip(detail_urls, home_dates)
            ]

        return [{"detail_url": detail_url, "img_url": None, "detail_date": None} for detail_url in detail_urls]

    def fetch_home_page(self, home_url: str):
        """抓取首页并按配置进行有限次重试。"""
        attempts = self.list_retry_count + 1
        for attempt in range(attempts):
            parsed_page = fetch_and_parse(home_url, wait_xpath=self.get_home_wait_xpath(home_url))
            if parsed_page:
                return parsed_page.get("parse_html")
            if attempt < attempts - 1:
                logger.warning(f"{home_url} 没有获取到数据, 尝试重试一次")
                time.sleep(self.list_retry_sleep_seconds)
        return None

    def build_res_record(self, home_url: str, detail_page, item: dict):
        """从详情页构建统一的入库结果字典。"""
        detail_url = item["detail_url"]
        detail_title_raw = self.extract_first_text(detail_page, self.get_title_xpath(home_url), "标题")

        detail_contents_list = self.extract_first_text_list(detail_page, self.get_content_xpath(home_url))
        detail_contents_raw = self.clean_text(self.content_joiner.join(detail_contents_list))

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
        for attempt in range(attempts):
            try:
                detail_parsed = fetch_and_parse(detail_url, wait_xpath=self.get_detail_wait_xpath(home_url))
                detail_page = detail_parsed.get("parse_html") if detail_parsed else None
                if detail_page is None:
                    raise ValueError("详情页解析失败")
                return self.build_res_record(home_url, detail_page, item)
            except Exception as e:
                if attempt < attempts - 1:
                    logger.warning(f"详情解析失败，准备重试一次: {detail_url}, error: {e}")
                    time.sleep(self.detail_retry_sleep_seconds)
                else:
                    logger.error(f"错误行: {e.__traceback__.tb_lineno}, error: {e}")
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
                    detail_content = (res.get("detail_contents") or res.get("detail_contents_cn") or "").strip()
                    if not detail_content:
                        logger.error(f"内容为空: {res.get('detail_url')}, {res.get('article_id')}")
                        continue
                    if self.min_content_length and len(detail_content) < self.min_content_length:
                        logger.warning(
                            f"内容长度不足{self.min_content_length}，跳过: {res.get('detail_url')}, "
                            f"length={len(detail_content)}"
                        )
                        continue
                    if self.max_content_length and len(detail_content) > self.max_content_length:
                        logger.warning(
                            f"内容长度超过{self.max_content_length}，跳过: {res.get('detail_url')}, "
                            f"length={len(detail_content)}"
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