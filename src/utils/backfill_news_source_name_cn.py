import sys
import pathlib
import argparse
import concurrent.futures
import functools

from loguru import logger
from sqlalchemy import text

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from src.main.config.manager import settings
from src.utils.db_tools import std_db
from src.utils.prod_db_tools import prod_db
from src.utils.source_name_mapping import map_source_name_cn_by_url


def ensure_column_exists(table_name: str, db_manager) -> None:
    """
    Ensure column news_source_name_cn exists in target table.
    """
    with db_manager._scoped_session() as session:
        check_sql = text(f"SHOW COLUMNS FROM {table_name} LIKE 'news_source_name_cn'")
        exists = session.execute(check_sql).fetchone()
        if exists:
            logger.info("Column news_source_name_cn already exists.")
            return

        alter_sql = text(f"ALTER TABLE {table_name} ADD COLUMN news_source_name_cn VARCHAR(255)")
        session.execute(alter_sql)
        session.commit()
        logger.info("Added column news_source_name_cn.")


def process_single_row(row, db_manager):
    table_name = settings.CRAWL_TABLE_NAME
    article_id = row[0]
    detail_url = row[1] or ""
    current_name = row[2] or ""

    mapped_name = map_source_name_cn_by_url(detail_url)

    if mapped_name == current_name:
        return "skip"

    with db_manager._scoped_session() as session:
        update_sql = text(
            f"UPDATE {table_name} SET news_source_name_cn = :news_source_name_cn WHERE article_id = :article_id"
        )
        session.execute(
            update_sql,
            {
                "news_source_name_cn": mapped_name,
                "article_id": article_id,
            },
        )
        session.commit()
    return "updated"


def backfill_news_source_name_cn(
    limit=None,
    force_update=False,
    max_workers=5,
    sort_order="desc",
    query_timeout_us=60000000,
    use_prod=False,
):
    table_name = settings.CRAWL_TABLE_NAME
    db_manager = prod_db if use_prod else std_db
    db_name = "prod_db" if use_prod else "std_db"

    ensure_column_exists(table_name, db_manager)

    with db_manager._scoped_session() as session:
        select_prefix = "SELECT"
        if getattr(settings, "DATABASE_TYPE", "").lower() == "oceanbase" and query_timeout_us:
            select_prefix = f"SELECT /*+ query_timeout({int(query_timeout_us)}) */"

        base_query = f"""
            {select_prefix}
                article_id,
                detail_url,
                news_source_name_cn
            FROM {table_name}
            WHERE detail_url IS NOT NULL AND detail_url != ''
        """

        if not force_update:
            base_query += " AND (news_source_name_cn IS NULL OR news_source_name_cn = '')"

        if sort_order and sort_order.lower() == "asc":
            base_query += " ORDER BY update_time ASC"
        else:
            base_query += " ORDER BY update_time DESC"

        if limit:
            base_query += f" LIMIT {int(limit)}"

        logger.info(f"Fetching rows for backfill from database: {db_name} ...")
        rows = session.execute(text(base_query)).fetchall()
        logger.info(f"Fetched {len(rows)} rows.")

    if not rows:
        logger.info("No rows to backfill.")
        return

    updated = 0
    skipped = 0

    logger.info(f"Start backfill with {max_workers} worker(s)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for result in executor.map(functools.partial(process_single_row, db_manager=db_manager), rows):
            if result == "updated":
                updated += 1
            else:
                skipped += 1

    logger.info(f"Backfill completed. updated={updated}, skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill news_source_name_cn by detail_url mapping.")
    parser.add_argument("--limit", type=int, help="Max rows to process. Default: all matched rows.")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing news_source_name_cn values.")
    parser.add_argument("--workers", type=int, default=5, help="Worker threads count. Default: 5.")
    parser.add_argument("--sort", type=str, default="desc", choices=["asc", "desc"], help="Sort by update_time.")
    parser.add_argument("--use-prod", action="store_true", help="Use production database instead of default database.")

    args = parser.parse_args()

    backfill_news_source_name_cn(
        limit=args.limit,
        force_update=args.force,
        max_workers=args.workers,
        sort_order=args.sort,
        use_prod=args.use_prod,
    )
