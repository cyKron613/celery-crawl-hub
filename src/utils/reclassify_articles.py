import sys
import pathlib
import time
from sqlalchemy import text
from loguru import logger
import argparse
import concurrent.futures

# Add project root to sys.path
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from src.main.config.manager import settings
from src.utils.db_tools import std_db
from src.utils.ai_tools import match_web_url_class_label

def process_single_article(row):
    """
    Process a single article row in a separate thread.
    """
    table_name = settings.CRAWL_TABLE_NAME
    article_id = row[0]
    title_cn = row[1]
    content_cn = row[2]
    title_en = row[3]
    content_en = row[4]
    current_class = row[5]
    
    # Prefer CN, fallback to EN
    if title_cn and content_cn:
        title = title_cn
        content = content_cn
    elif title_en and content_en:
        title = title_en
        content = content_en
    else:
        logger.warning(f"Skipping article {article_id}: insufficient content.")
        return

    logger.info(f"Processing article {article_id}: {title[:20]}...")
    
    try:
        # Call the classification function
        new_class = match_web_url_class_label(title, content)
        
        # Update if changed or if it was empty
        if new_class != current_class:
            # Use a new session for the update in this thread
            with std_db._scoped_session() as session:
                update_sql = text(f"UPDATE {table_name} SET class_level_1 = :new_class WHERE article_id = :article_id")
                session.execute(update_sql, {'new_class': new_class, 'article_id': article_id})
                session.commit()
            logger.info(f"Updated article {article_id}: '{current_class}' -> '{new_class}'")
        else:
            logger.info(f"Article {article_id} class unchanged: '{new_class}'")
            
        # Sleep briefly to avoid hitting API rate limits too hard
        time.sleep(0.5)
            
    except Exception as e:
        logger.error(f"Failed to re-classify article {article_id}: {e}")

def reclassify_articles(limit=None, force_update=False, max_workers=1, sort_order='desc', query_timeout_us=60000000):
    """
    Re-classify articles in the database and update class_level_1.
    
    Args:
        limit (int): Max number of articles to process.
        force_update (bool): If True, re-classify even if class_level_1 is already set.
                             If False, only update where class_level_1 is NULL or empty.
        max_workers (int): Number of threads to use.
        sort_order (str): 'asc' or 'desc' for sorting by detail_date.
    """
    table_name = settings.CRAWL_TABLE_NAME
    
    rows = []
    try:
        with std_db._scoped_session() as session:
            # Build query
            # We select articles that have content to classify (either CN or EN)
            select_prefix = "SELECT"
            if getattr(settings, "DATABASE_TYPE", "").lower() == "oceanbase" and query_timeout_us:
                select_prefix = f"SELECT /*+ query_timeout({int(query_timeout_us)}) */"

            base_query = f"""
                {select_prefix} article_id, detail_title_cn, detail_contents_cn, detail_title, detail_contents, class_level_1 
                FROM {table_name} 
                WHERE (detail_title_cn IS NOT NULL AND detail_contents_cn != '') 
                   OR (detail_title IS NOT NULL AND detail_contents != '')
            """
            
            if not force_update:
                base_query += " AND (class_level_1 IS NULL OR class_level_1 = '')"
            
            # Add sorting
            if sort_order and sort_order.lower() == 'asc':
                base_query += " ORDER BY update_time ASC"
            else:
                base_query += " ORDER BY update_time DESC"

            if limit:
                base_query += f" LIMIT {limit}"
                
            logger.info(f"Executing query to fetch articles...")
            result = session.execute(text(base_query))
            rows = result.fetchall()
            
            logger.info(f"Found {len(rows)} articles to re-classify.")
            
    except Exception as e:
        logger.error(f"Database error during fetch: {e}")
        raise

    # Process rows using ThreadPoolExecutor
    if rows:
        logger.info(f"Starting processing with {max_workers} workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(process_single_article, rows)
        logger.info("All tasks completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-classify articles in the database.")
    parser.add_argument("--limit", type=int, default=10, help="Limit the number of articles to process. Default is 10.")
    parser.add_argument("--force", action="store_true", help="Force re-classification of all articles (within limit), even if they already have a class.")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker threads. Default is 1.")
    parser.add_argument("--sort", type=str, default="desc", choices=['asc', 'desc'], help="Sort by detail_date. Default is desc.")
    
    args = parser.parse_args()
    
    reclassify_articles(limit=args.limit, force_update=args.force, max_workers=args.workers, sort_order=args.sort)
