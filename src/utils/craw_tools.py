import pathlib
import functools
import json
import sys
import uuid
from typing import List, Optional, Union
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from loguru import logger
from src.utils.chromium_manager import ChromiumOptionsManager
from src.utils.playwright_manager import playwright_fetch
from src.utils.db_tools import std_db
from src.utils.ai_tools import match_web_url_class_label_2
from src.utils.source_name_mapping import map_source_name_cn_by_url

from src.main.config.manager import settings

from concurrent.futures import ThreadPoolExecutor
from fake_useragent import UserAgent
from DrissionPage import ChromiumPage
from lxml import etree
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from urllib.parse import urlparse

# 导入PostgreSQL异常类
try:
    import psycopg2
    from psycopg2 import errors
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

import time
# from src.utils.data_obs_operator import HuaWeiObsClient

ua = UserAgent()
# obs = HuaWeiObsClient()

table_name = settings.CRAWL_TABLE_NAME
log_table_name = settings.CRAWLER_LOG_TABLE_NAME
insert_into_sdc = settings.INSERT_INTO_SDC
log_table_name_detail = settings.CRAWLER_LOG_DETAIL_TABLE_NAME
insert_into_prod = settings.INSERT_INTO_PROD

if insert_into_sdc:
    # 如果需要插入到SDC表，导入SDC数据库连接
    from src.utils.sdc_db_tools import sdc_db
    from src.utils.ai_tools import sdc_match_web_url_class_label
    sdc_table_name = settings.SDC_TABLE_NAME

if insert_into_prod:
    # 如果需要插入到生产库表，导入生产库数据库连接
    from src.utils.prod_db_tools import prod_db


def record_task_log(website_name, base_url, log_msg):
    """
    记录任务执行日志到数据库
    """
    try:
        with std_db._scoped_session() as session:
            log_stmt = text(f"INSERT INTO {log_table_name_detail} (website_name, base_url, crawl_detail_log) VALUES (:website_name, :base_url, :crawl_detail_log)")
            session.execute(log_stmt, {
                'website_name': website_name,
                'base_url': base_url,
                'crawl_detail_log': log_msg
            })
            session.commit()

            if insert_into_prod:
                with prod_db._scoped_session() as prod_session:
                    prod_session.execute(log_stmt, {
                        'website_name': website_name,
                        'base_url': base_url,
                        'crawl_detail_log': log_msg
                    })
                    prod_session.commit()

            logger.info(f"成功记录任务日志: {website_name}")
    except Exception as e:
        logger.error(f"记录任务日志失败: {e}")


def task_logging_decorator(website_name, base_url):
    """
    任务执行日志装饰器
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                # 记录完整结果或错误信息
                if result and isinstance(result, list):
                    log_content = json.dumps(result, ensure_ascii=False)
                else:
                    log_content = result
                
                record_task_log(website_name, base_url, log_content)
                return result
            except Exception as e:
                # 记录错误日志
                error_msg = f"任务执行失败: {str(e)}"
                record_task_log(website_name, base_url, error_msg)
                raise e
        return wrapper
    return decorator


def update_no_translate_context(table_name, abstract_cn, abstract,
                                detail_title_cn, detail_contents_cn,
                                detail_contents, detail_title,
                                article_id,
                                keyword1, keyword2, keyword3, is_translated, db=None):
    # 创建一个同步会话对象
    if db is None:
        db = std_db
    try:
        with db._scoped_session() as session:
            # 使用参数化查询来避免 SQL 注入
            exe_sql = text(f"""
                UPDATE {table_name}
                SET
                    abstract_cn = :abstract_cn,
                    abstract = :abstract,
                    detail_title_cn = :detail_title_cn,
                    detail_contents_cn = :detail_contents_cn,
                    detail_contents = :detail_contents,
                    detail_title = :detail_title,
                    is_translated = :is_translated,
                    keyword1 = :keyword1,
                    keyword2 = :keyword2,
                    keyword3 = :keyword3
                WHERE
                    article_id = :article_id
            """)

            session.execute(exe_sql, {
                'abstract_cn': abstract_cn,
                'abstract': abstract,
                'detail_title_cn': detail_title_cn,
                'detail_contents_cn': detail_contents_cn,
                'detail_contents': detail_contents,
                'detail_title': detail_title,
                'article_id': article_id,
                'keyword1': keyword1,
                'keyword2': keyword2,
                'keyword3': keyword3,
                'is_translated': is_translated
            })
            logger.info(f"已更新id： {article_id}")
            session.commit()

    except Exception as e:
        logger.error(f"{e}, 在更新未翻译上下文时发生错误")
        raise

def delete_high_risk_data(table_name, article_id, db=None):
    """
    删除指定article_id的数据行。
    """
    # 创建一个同步会话对象
    if db is None:
        db = std_db
    try:
        with db._scoped_session() as session:
            # 使用参数化查询来避免SQL注入
            exe_sql = text(f"""
                DELETE FROM {table_name}
                WHERE
                    article_id = :article_id
            """)

            session.execute(exe_sql, {'article_id': article_id})
            logger.info(f"已删除高风险数据： {article_id}")
            session.commit()

    except Exception as e:
        logger.error(f"{e}, 在删除数据时发生错误")
        raise


def _is_connection_lost_error(exception):
    if isinstance(exception, (OperationalError, DBAPIError)):
        if getattr(exception, "connection_invalidated", False):
            return True

    message = str(exception).lower()
    connection_error_markers = [
        "server has gone away",
        "connection reset by peer",
        "lost connection",
        "connection was killed",
        "connection refused",
        "broken pipe",
    ]
    return any(marker in message for marker in connection_error_markers)


def _fetch_untranslated_rows(session, table_name):
    exe_sql = f"""
        SELECT detail_title, detail_contents, article_id, detail_url
        FROM {table_name}
        WHERE is_translated = 'no'
        AND detail_title IS NOT NULL;
    """
    result = session.execute(text(exe_sql))
    rows = result.fetchall()
    translate_result = [{"detail_title": row[0], "detail_contents": row[1], "article_id": row[2], "detail_url": row[3]}
        for row in rows]

    exe_sql2 = f"""
        SELECT detail_title_cn, detail_contents_cn, article_id, detail_url
        FROM {table_name}
        WHERE is_translated = 'no'
        AND detail_title_cn IS NOT NULL;
    """
    result = session.execute(text(exe_sql2))
    rows = result.fetchall()
    translate_result_cn = [{"detail_title_cn": row[0], "detail_contents_cn": row[1], "article_id": row[2], "detail_url": row[3]}
        for row in rows]

    translate_result.extend(translate_result_cn)
    return translate_result

def find_translated(table_name, db=None):
    if db is None:
        db = std_db
    for attempt in range(2):
        try:
            with db._scoped_session() as session:
                return _fetch_untranslated_rows(session, table_name)
        except Exception as e:
            if attempt == 0 and _is_connection_lost_error(e):
                logger.warning(f"查询未翻译数据时连接断开，准备重试一次: {e}")
                if getattr(db, "_scoped_session", None):
                    db._scoped_session.remove()
                continue
            logger.error(f"{e}, {e.__traceback__.tb_lineno}")
            raise

def get_primary_key(web_name, res_dict):
    try:
        primary_key = web_name + '_' + res_dict.get('detail_date').split(' ')[0].replace('-', '') + '_' + res_dict.get(
            'detail_title')[:4] + res_dict.get('detail_title')[-4:]
        return primary_key
    except Exception:
        try:
            primary_key = web_name + '_' + res_dict.get('detail_date').split(' ')[0].replace('-',
                                                                                             '') + '_' + res_dict.get(
                'detail_title_cn')[:4] + res_dict.get('detail_title_cn')[-4:]
            return primary_key
        except Exception as e:
            logger.error(e)
            return None

def _ensure_xpath_list(xpath_value: Union[str, List[str], tuple, None]) -> List[str]:
    if not xpath_value:
        return []
    if isinstance(xpath_value, str):
        return [xpath_value]
    return [xpath for xpath in xpath_value if xpath]


def wait_for_xpath_or_timeout(tab, wait_xpath: Union[str, List[str]], wait_seconds: float = 10, poll_interval: float = 0.5):
    wait_xpaths = _ensure_xpath_list(wait_xpath)
    if not wait_xpaths:
        return
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        try:
            html = tab.html
            if html:
                parsed_html = etree.HTML(html)
                if parsed_html is not None:
                    for xpath in wait_xpaths:
                        if parsed_html.xpath(xpath):
                            logger.info(f"页面已命中等待xpath: {xpath}")
                            return
        except Exception:
            pass
        time.sleep(poll_interval)


def get_with_timeout(url, need_click, chromium_options_manager, timeout=30, wait_xpath: Optional[Union[str, List[str]]] = None):
    """
    使用DrissionPage获取页面内容，支持超时和重试
    :param url: 目标URL
    :param need_click: 是否需要点击页面元素
    :param timeout: 超时时间
    :return: 包含html和状态的字典
    """
    local_web_status = {'html': None, 'status': False}
    
    try:
        headers = {
            'User-Agent': ua.random,
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://www.google.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        }
        
        # 使用 ChromiumOptionsManager 的上下文管理器，确保浏览器无论成功与否都会关闭
        with chromium_options_manager.chromium_page() as page:
            # 设置页面加载超时
            page.set.timeouts(page_load=timeout)
            
            page.run_js("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            tab = page.new_tab()
            # 设置标签页超时
            tab.set.timeouts(page_load=timeout)
            
            # 添加模拟请求头
            tab.set.headers(headers)
            
            # get 方法也设置超时
            tab.get(url=url, retry=0, interval=0)
            
            if wait_xpath:
                wait_for_xpath_or_timeout(tab, wait_xpath)
            else:
                time.sleep(5)  # 稍微等待加载
            tab.stop_loading()

            html = tab.html
            if html:
                local_web_status['html'] = html
                local_web_status['status'] = True
            
            # 显式关闭标签页
            try:
                tab.close()
            except:
                pass
                
        return local_web_status

    except Exception as e:
        logger.error(f"爬取失败: {url}, 错误: {str(e)}")
        return local_web_status

def fetch_and_parse(
    url: str,
    need_click: bool = False,
    max_retries: int = 2,
    retry_delay: int = 1,
    timeout: float = 300,
    wait_xpath: Optional[Union[str, List[str]]] = None,
):
    """
    优化后的爬虫函数，直接调用避免线程池开销
    :param url: 目标URL
    :param need_click: 是否需要点击页面元素
    :param max_retries: 最大重试次数
    :param retry_delay: 重试延迟基数(秒)
    :param timeout: 单次请求超时时间(秒)
    :param wait_xpath: 可选，等待命中的xpath；未传时保持原有固定等待逻辑
    :return: 包含html和解析结果的字典
    """
    logger.info(f"fetch_and_parse_normal解析失败，使用fetch_and_parse解析: {url}")
    
    # 支持双渲染引擎切换
    engine = settings.CRAWL_ENGINE.lower()
    if engine == "playwright":
        logger.info(f"使用 Playwright 引擎渲染: {url}")
        for attempt in range(max_retries):
            try:
                # Playwright 异步逻辑在同步 worker 中由于已经存在 event loop 或没有 event loop，
                # 我们通过 asyncio.run 执行
                import asyncio
                result = asyncio.run(playwright_fetch(url, timeout, wait_xpath, need_click))
                
                if result and result.get('status'):
                    html = result.get('html')
                    if html:
                        return {
                            "cur_url": result.get('url', url),
                            "html": html,
                            "parse_html": etree.HTML(html),
                            "status": True
                        }
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                continue
            except Exception as e:
                logger.error(f"Playwright attempt {attempt+1} 失败: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
        return {"status": False, "error": "Playwright failed after retries"}

    # 原有 DrissionPage 逻辑
    chromium_options_manager = ChromiumOptionsManager()
    
    for attempt in range(max_retries):
        try:
            logger.info(f'开始第{attempt+1}次尝试: {url}, 超时时间: {timeout}秒')
            
            # 使用线程池 timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(get_with_timeout, url, need_click, chromium_options_manager, timeout, wait_xpath)
                result = future.result(timeout=timeout)
            
                if result and result.get('status'):
                    html = result.get('html')
                    if html:
                        return {
                            "cur_url": url,
                            "html": html,
                            "parse_html": etree.HTML(html),
                            "status": True
                        }
                    raise ValueError(f'获取到空HTML内容: {url}')
                
                raise RuntimeError(f'请求失败: {url}, 超时!')

        except Exception as e:
            logger.warning(f"第{attempt+1}次尝试失败: {url}, 错误: {str(e)}")
            if attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1)
                logger.info(f"{delay}秒后重试...")
                time.sleep(delay)
                continue
            raise TimeoutError(f"所有{max_retries}次尝试均失败: {url}")

def get_base_url_simple(url):
    """
    获取基础URL的简洁版本
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _ensure_row_uuid(item):
    current_uuid = item.get("uuid")
    if current_uuid is None:
        item["uuid"] = str(uuid.uuid4())
        return

    normalized_uuid = str(current_uuid).strip()
    if not normalized_uuid or normalized_uuid.lower() == "uuid()":
        item["uuid"] = str(uuid.uuid4())


def insert_into_table(data: list[dict] = None, wechat_news_name: str = None):
    """
    插入数据到指定表
    
    Args:
        table_name: 表名
        data: 要插入的数据字典列表
    """
    session = None
    sdc_session = None
    prod_session = None

    try:
        successful_inserts = 0
        sdc_successful_inserts = 0
        prod_successful_inserts = 0

        session = std_db._scoped_session()
        base_url = get_base_url_simple(data[0].get('detail_url', '')) if data else ''

        if base_url == 'http://mp.weixin.qq.com':
            news_name = wechat_news_name
        else:
            news_name = data[0].get('article_id', 'Unknown').split('_')[0] if data else 'Unknown'

        for item in data:
            try:
                _ensure_row_uuid(item)

                # 新增class_level_2的分类
                detail_title = item.get('detail_title', '') or item.get('detail_title_cn', '')
                detail_contents = item.get('detail_contents', '') or item.get('detail_contents_cn', '')
                detail_url = item.get('detail_url', '')
                class_level_1 = item.get('class_level_1', '')
                item['news_source_name_cn'] = item.get('news_source_name_cn') or map_source_name_cn_by_url(detail_url)
                item['class_level_2'] = match_web_url_class_label_2(
                    detail_title, detail_contents, detail_url, class_level_1
                )
                
                # 获取 SDC 会话，失败时只记录日志，不中断主流程
                if insert_into_sdc:
                    try:
                        sdc_session = sdc_db._scoped_session()
                    except Exception as e:
                        logger.error(f"获取 SDC 数据库会话失败，跳过写入 SDC：{e}")
                        sdc_session = None

                # 获取生产库会话，失败时只记录日志，不中断主流程
                if insert_into_prod and prod_session is None:
                    try:
                        prod_session = prod_db._scoped_session()
                    except Exception as e:
                        logger.error(f"获取生产库会话失败，跳过写入生产库：{e}")
                        prod_session = None

                stmt = text(f"SELECT 1 FROM {table_name} WHERE article_id = :article_id")
                # 先判断是否存在重复键值
                result = session.execute(stmt, {'article_id': item['article_id']}).fetchone()

                if result:
                    logger.warning(f"数据已存在，跳过插入（重复键值）: {item.get('article_id', 'Unknown')}")
                else:
                    try:
                        if "update_time" in item:
                            del item["update_time"] # 使用默认值
                        stmt = text(f"INSERT INTO {table_name} ({', '.join(item.keys())}) VALUES ({', '.join([':' + k for k in item.keys()])})")
                        session.execute(stmt, item)
                        successful_inserts += 1
                    except Exception as e:
                        logger.error(f"插入数据 {item} 到表 {table_name} 失败: {e}")
                        session.rollback()
                        raise

                if insert_into_sdc and sdc_session is not None:
                    exist_stmt = text(f"SELECT 1 FROM {sdc_table_name} WHERE article_id = :article_id")
                    result_sdc = sdc_session.execute(exist_stmt, {'article_id': item['article_id']}).fetchone()
                    if result_sdc:
                        logger.warning(f"SDC数据已存在，跳过插入（重复键值）: {item.get('article_id', 'Unknown')}")
                    else:
                        try:
                            # 重新分类
                            if item.get("article_id").startswith('aibase'):
                                item['class_level_1'] = '科技前沿'
                            elif item.get('detail_title') and item.get('detail_contents'):
                                item['class_level_1'] = sdc_match_web_url_class_label(item.get('detail_title', ''), item.get('detail_contents', ''))
                            elif item.get('detail_title_cn') and item.get('detail_contents_cn'):
                                item['class_level_1'] = sdc_match_web_url_class_label(item.get('detail_title_cn', ''), item.get('detail_contents_cn', ''))
                            else:
                                pass

                            # 插入SDC表
                            sdc_stmt = text(f"""INSERT INTO {sdc_table_name} ({', '.join(item.keys())}) VALUES ({', '.join([':' + k for k in item.keys()])})""")
                            sdc_session.execute(sdc_stmt, item)
                            sdc_successful_inserts += 1
                        except Exception as e:
                            logger.error(f"插入数据 {item} 到SDC表 {sdc_table_name} 失败: {e}")
                            sdc_session.rollback()
                            raise

                if insert_into_prod and prod_session is not None:
                    try:
                        exist_stmt_prod = text(f"SELECT 1 FROM {table_name} WHERE article_id = :article_id")
                        result_prod = prod_session.execute(exist_stmt_prod, {'article_id': item['article_id']}).fetchone()
                        if result_prod:
                            logger.warning(f"生产库数据已存在，跳过插入（重复键值）: {item.get('article_id', 'Unknown')}")
                        else:
                            try:
                                prod_stmt = text(f"INSERT INTO {table_name} ({', '.join(item.keys())}) VALUES ({', '.join([':' + k for k in item.keys()])})")
                                prod_session.execute(prod_stmt, item)
                                prod_successful_inserts += 1
                            except Exception as e:
                                logger.error(f"插入数据 {item} 到生产库表 {table_name} 失败: {e}")
                                prod_session.rollback()
                    except Exception as e:
                        logger.error(f"检查或写入生产库失败（仅记录日志，任务继续）：{e}")
                        try:
                            prod_session.rollback()
                        except Exception as rollback_error:
                            logger.error(f"生产库回滚失败（仅记录日志，任务继续）：{rollback_error}")

            except Exception as e:
                logger.error(f"写入出现异常: {e}， 异常行： {e.__traceback__.tb_lineno}")
                # 对于其他异常，回滚并重新抛出（生产库相关异常已在上面吞掉）
                session.rollback()
                if sdc_session:
                    sdc_session.rollback()
                # 生产库异常已在各自代码块中处理，这里不再因为生产库问题中断任务
    
        # 只有所有插入都成功或跳过重复项后才提交
        session.commit()
        logger.info(f"成功插入 {successful_inserts} 条数据到表 {table_name}")
        if insert_into_sdc and sdc_session is not None:
            try:
                sdc_session.commit()
                logger.info(f"成功插入 {sdc_successful_inserts} 条数据到SDC表 {sdc_table_name}")
            except Exception as e:
                logger.error(f"提交 SDC 事务失败：{e}")
        
        if insert_into_prod and prod_session is not None:
            try:
                prod_session.commit()
                logger.info(f"成功插入 {prod_successful_inserts} 条数据到生产库表 {table_name}")
            except Exception as e:
                logger.error(f"提交生产库事务失败（仅记录日志，任务继续）：{e}")
                try:
                    prod_session.rollback()
                except Exception as rollback_error:
                    logger.error(f"生产库回滚失败（仅记录日志，任务继续）：{rollback_error}")

        
        # 插入日志
        try:
            if successful_inserts == 0:
                log_msg = "无新数据插入"
            else:
                log_msg = f"成功同步 {successful_inserts} 条数据"

            log_stmt = text(f"INSERT INTO {log_table_name} (website_name, base_url, crawl_log) VALUES (:website_name, :base_url, :crawl_log)")
            
            session.execute(log_stmt, {
                'website_name': news_name,
                'base_url': base_url,
                'crawl_log': log_msg
            })
            session.commit()

            if insert_into_prod:
                try:
                    if prod_session is None:
                        try:
                            prod_session = prod_db._scoped_session()
                        except Exception as e:
                            logger.error(f"获取生产库会话失败，跳过写入生产库日志：{e}")
                            prod_session = None

                    if prod_session is not None:
                        prod_session.execute(log_stmt, {
                            'website_name': news_name,
                            'base_url': base_url,
                            'crawl_log': log_msg
                        })
                        prod_session.commit()
                except Exception as e:
                    logger.error(f"插入日志到生产库表 {log_table_name} 失败（仅记录日志，任务继续）：{e}")
                    if prod_session is not None:
                        try:
                            prod_session.rollback()
                        except Exception as rollback_error:
                            logger.error(f"生产库日志回滚失败（仅记录日志，任务继续）：{rollback_error}")

        except Exception as e:
            logger.error(f"插入日志到表 {log_table_name} 失败: {e}")

            

    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"插入数据到表 {table_name} 失败: {e}")
        raise
    finally:
        if session:
            session.close()
        if sdc_session:
            sdc_session.close()
        if prod_session:
            prod_session.close()



if __name__ == '__main__':
    translate_result = find_translated('sdc_data.ex_shipping_information')
    print(translate_result)