import sys
import time
from loguru import logger
from concurrent.futures import ThreadPoolExecutor
import pathlib
ROOT_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
sys.path.append(str(ROOT_DIR))
print(f"ROOT_DIR: {ROOT_DIR}")

from src.utils.craw_tools import find_translated as translate
from src.utils.craw_tools import update_no_translate_context as update_table
from src.utils.craw_tools import delete_high_risk_data as delete_data
from src.utils.ai_tools import report_for_en, translate_content, translate_title, \
    for_simple_analyze_report, catch_hot_key_words, llm_filter_high_risk_news, TranslationTimeoutError
from celery import shared_task
from src.main.config.manager import settings

table_name = settings.CRAWL_TABLE_NAME


@shared_task(name="translate_tasks.time_task", soft_time_limit=None, time_limit=None)
def time_task():
    # 1. 处理默认库
    try:
        translate_list = translate(table_name)
        logger.info(f'默认库 translate_obj: {len(translate_list)}')
        process_list(translate_list)
    except Exception as e:
        logger.error(f"默认库翻译任务执行失败: {e}")

    # 2. 如果开启生产库写入，则处理生产库
    if settings.INSERT_INTO_PROD:
        try:
            from src.utils.prod_db_tools import prod_db
            logger.info("开始处理生产库翻译任务...")
            prod_translate_list = translate(table_name, db=prod_db)
            logger.info(f'生产库 translate_obj: {len(prod_translate_list)}')
            process_list(prod_translate_list, db=prod_db)
        except Exception as e:
            logger.error(f"生产库翻译任务执行失败: {e}")


def process_list(translate_list, db=None):
    """
    处理翻译列表
    """
    # 使用线程池来并行执行任务
    with ThreadPoolExecutor(5) as executor:  # 你可以根据需要调整线程数
        futures = []
        for item in translate_list:
            future = executor.submit(process_item, item, db=db)
            futures.append(future)
        for future in futures:
            try:
                future.result()  # 这会等待每个任务完成
            except Exception as e:
                logger.error(f"{e}, {e.__traceback__.tb_lineno}")
                # 针对429（超限）类型报错 休眠一分钟
                if "429" in str(e):
                    time.sleep(60)
                continue


def is_high_risk_exception(raised_exception):
    if "high risk" in str(raised_exception) or "inappropriate content." in str(raised_exception):
        return True
    else:
        return False


def is_translation_timeout_exception(raised_exception):
    return isinstance(raised_exception, TranslationTimeoutError)


def process_item(item, db=None):
    article_id = item.get("article_id")
    detail_title = item.get("detail_title")
    detail_contents = item.get("detail_contents") or item.get("detail_title_cn")
    
    is_high_risk = llm_filter_high_risk_news(detail_title, detail_contents)
    if is_high_risk.strip() == '【直接过滤】':
        delete_data(table_name, article_id, db=db)
        logger.info(f"第一次安全检查... 删除高风险数据: {article_id}")
        return
 

    try:
        if not detail_title:
            detail_title_cn = item.get("detail_title_cn")
            detail_title = translate_title(detail_title_cn, 'zh')
        else:
            detail_title_cn = translate_title(detail_title, 'en')

        # 微信热点需求, 英文
        detail_contents = item.get("detail_contents")
        # 英文翻译成中文
        if not detail_contents:
            # 如果获取不到detail_content 说明是中文版本
            detail_contents_cn = item.get("detail_contents_cn")
            # 中文翻译成英文
            detail_contents = translate_content(detail_contents_cn, 'zh')
        else:
            detail_contents_cn = translate_content(detail_contents, 'en')

        # abstract_cn_wechat = for_analyze_report(detail_contents)
        # 新闻需求, prompt已兼容中文版本。
        abstract_cn = for_simple_analyze_report(detail_contents)
        # 中文摘要英译
        abstract_en = report_for_en(abstract_cn)

        # 热点关键字， 返回英文版本
        keyword1, keyword2, keyword3 = eval(catch_hot_key_words(detail_contents, detail_title))

        # 如果每一项翻译都成功不为空
        is_translated = "yes"

        update_table(table_name, abstract_cn, abstract_en,
                     detail_title_cn, detail_contents_cn,
                     detail_contents, detail_title,
                     article_id, keyword1, keyword2, keyword3, is_translated, db=db)

    except Exception as e:
        logger.error(f"error occured: {e}, {e.__traceback__.tb_lineno}")
        if is_translation_timeout_exception(e):
            delete_data(table_name, article_id, db=db)
            logger.info(f"翻译超时... 删除新闻数据: {article_id}")
            return
        if is_high_risk_exception(e):
            delete_data(table_name, article_id, db=db)
            logger.info(f"输出安全检查...   删除高风险数据: {article_id}")
            return


if __name__ == '__main__':
    time_task()
