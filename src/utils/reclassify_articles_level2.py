import sys
import pathlib
import time
from sqlalchemy import text
from loguru import logger
import argparse
import concurrent.futures
import functools

# Add project root to sys.path
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from src.main.config.manager import settings
from src.utils.db_tools import std_db
from src.utils.prod_db_tools import prod_db
from src.utils.ai_tools import match_web_url_class_label_2


def _parse_level2_tags(raw: str) -> list[str]:
    """
    Parse class_level_2 string like '[集团内部, 国际, 集运市场]' into a list of tags.
    Handles both bracket-wrapped and plain comma-separated formats.
    """
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("["):
        raw = raw[1:]
    if raw.endswith("]"):
        raw = raw[:-1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def _build_level2_str(tags: list[str]) -> str:
    return "[" + ", ".join(tags) + "]" if tags else ""


def process_single_article(row, db_manager):
    """
    Process a single article row: generate class_level_2 and write to DB.
    """
    table_name = settings.CRAWL_TABLE_NAME
    article_id   = row[0]
    title_cn     = row[1]
    content_cn   = row[2]
    title_en     = row[3]
    content_en   = row[4]
    class_level_1 = row[5] or ""
    detail_url   = row[6] or ""

    # Prefer CN content, fallback to EN
    if title_cn and content_cn:
        title   = title_cn
        content = content_cn
    elif title_en and content_en:
        title   = title_en
        content = content_en
    else:
        logger.warning(f"Skipping article {article_id}: insufficient content.")
        return

    logger.info(f"Processing article {article_id}: {title[:30]}...")

    try:
        new_level2 = match_web_url_class_label_2(
            news_title=title,
            news_content=content,
            news_source=detail_url,
            level1_label=class_level_1,
        )

        # todo: 可以在这里添加一些校验逻辑，确保 new_level2 的格式正确，或者符合预期的标签集合等
        # _parse_level2_tags(new_level2)  # 如果格式不对，这里会抛异常

        with db_manager._scoped_session() as session:
            update_sql = text(
                f"UPDATE {table_name} SET class_level_2 = :new_level2 WHERE article_id = :article_id"
            )
            session.execute(update_sql, {"new_level2": new_level2, "article_id": article_id})
            session.commit()

        logger.info(f"Updated article {article_id} class_level_2 -> {new_level2}")

        # Brief sleep to avoid API rate-limit bursts
        time.sleep(0.5)

    except Exception as e:
        logger.error(f"Failed to classify article {article_id}: {e}")


def reclassify_articles_level2(
    limit=None,
    force_update=False,
    max_workers=1,
    sort_order="desc",
    query_timeout_us=60000000,
    use_prod=False,
):
    """
    Re-classify articles in the database and update class_level_2.

    Args:
        limit (int):            Max number of articles to process.
        force_update (bool):    If True, overwrite existing class_level_2 values.
                                If False, only process rows where class_level_2 is NULL/empty.
        max_workers (int):      Number of concurrent worker threads.
        sort_order (str):       'asc' or 'desc' - ordering by update_time.
        query_timeout_us (int): OceanBase query timeout in microseconds.
    """
    table_name = settings.CRAWL_TABLE_NAME
    db_manager = prod_db if use_prod else std_db
    db_name = "prod_db" if use_prod else "std_db"

    rows = []
    try:
        with db_manager._scoped_session() as session:
            select_prefix = "SELECT"
            if getattr(settings, "DATABASE_TYPE", "").lower() == "oceanbase" and query_timeout_us:
                select_prefix = f"SELECT /*+ query_timeout({int(query_timeout_us)}) */"

            base_query = f"""
                {select_prefix}
                    article_id,
                    detail_title_cn,
                    detail_contents_cn,
                    detail_title,
                    detail_contents,
                    class_level_1,
                    detail_url
                FROM {table_name}
                WHERE (
                    (detail_title_cn IS NOT NULL AND detail_contents_cn != '')
                    OR (detail_title IS NOT NULL AND detail_contents != '')
                )
            """

            # base_query += " AND class_level_1 = '航运市场'"
            # base_query += " AND article_id = 'splash_20251104_Fujitong'"

            if not force_update:
                base_query += " AND (class_level_2 IS NULL OR class_level_2 = '')"

            if sort_order and sort_order.lower() == "asc":
                base_query += " ORDER BY update_time ASC"
            else:
                base_query += " ORDER BY update_time DESC"

            if limit:
                base_query += f" LIMIT {limit}"

            logger.info(f"Fetching articles from database: {db_name} ...")
            result = session.execute(text(base_query))
            rows = result.fetchall()
            logger.info(f"Found {len(rows)} articles to process.")

    except Exception as e:
        logger.error(f"Database error during fetch: {e}")
        raise

    if rows:
        logger.info(f"Starting classification with {max_workers} worker(s)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(functools.partial(process_single_article, db_manager=db_manager), rows)
        logger.info("All tasks completed.")
    else:
        logger.info("No articles to process.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-classify articles: write class_level_2 using LLM.")
    parser.add_argument("--limit",   type=int,
                        help="Max number of articles to process no default is set, meaning process all matching articles.")
    parser.add_argument("--force",   action="store_true",
                        help="Force re-classification even if class_level_2 already set.")
    parser.add_argument("--workers", type=int, default=10,
                        help="Number of worker threads. Default: 10.")
    parser.add_argument("--sort",    type=str, default="desc", choices=["asc", "desc"],
                        help="Sort order by update_time. Default: desc.")
    parser.add_argument("--use-prod", action="store_true",
                        help="Use production database instead of default database.")

    args = parser.parse_args()

    reclassify_articles_level2(
        limit=args.limit,
        force_update=args.force,
        max_workers=args.workers,
        sort_order=args.sort,
        use_prod=args.use_prod, 
    )
