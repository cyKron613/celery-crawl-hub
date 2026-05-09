import sys
import pathlib
import time
import os
import requests
import tempfile
import uuid
from urllib.parse import urlparse
from sqlalchemy import text
from loguru import logger
import urllib3
import concurrent.futures

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add project root to sys.path
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from src.main.config.manager import settings
from src.utils.db_tools import std_db
from src.utils.data_obs_operator import HuaWeiObsClient

DEFAULT_IMG_URL = 'https://ai-doc.data.myvessel.cn/news/%E8%88%AA%E8%BF%90%E5%BF%AB%E8%AE%AF%E5%A4%B4%E5%9B%BE.jpg?OSSAccessKeyId=LTAI5t7nfdMfD7YeTFpAENJ4&Expires=2725518616&Signature=Tw08oPC0RL%2FKweHU1Q1NlJZhZHA%3D'
DEFAULT_IMG_PATH = os.path.join(tempfile.gettempdir(), "default_news_img.jpg")

def ensure_default_image_exists():
    if os.path.exists(DEFAULT_IMG_PATH):
        return True
    
    try:
        logger.info(f"Downloading default image to {DEFAULT_IMG_PATH}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(DEFAULT_IMG_URL, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        with open(DEFAULT_IMG_PATH, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.error(f"Failed to download default image: {e}")
        return False

def get_filename_from_url(url):
    try:
        parsed = urlparse(url)
        path = parsed.path
        filename = os.path.basename(path)
        if not filename:
            return f"{uuid.uuid4()}.jpg"
        return filename
    except:
        return f"{uuid.uuid4()}.jpg"

def process_single_article(row):
    article_id = row[0]
    img_url = row[1]
    table_name = settings.CRAWL_TABLE_NAME
    
    # 每个线程实例化一个 OBS 客户端，确保线程安全
    obs_client = HuaWeiObsClient()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    content = None
    
    # 简单的去重或校验
    if not img_url or not img_url.startswith('http'):
        logger.warning(f"Invalid img_url for article {article_id}: {img_url}")
        # 使用默认图片
        if ensure_default_image_exists():
            try:
                with open(DEFAULT_IMG_PATH, 'rb') as f:
                    content = f.read()
                
                # 更新 img_parse_url 为默认图片
                with std_db._scoped_session() as session:
                    update_img_sql = text(f"UPDATE {table_name} SET img_parse_url = :default_url WHERE article_id = :article_id")
                    session.execute(update_img_sql, {'default_url': DEFAULT_IMG_URL, 'article_id': article_id})
                    session.commit()
            except Exception as e:
                logger.error(f"Failed to read default image or update db for article {article_id}: {e}")
                with std_db._scoped_session() as session:
                    update_sql = text(f"UPDATE {table_name} SET obs_url = 'FAILED' WHERE article_id = :article_id")
                    session.execute(update_sql, {'article_id': article_id})
                    session.commit()
                return
        else:
            with std_db._scoped_session() as session:
                update_sql = text(f"UPDATE {table_name} SET obs_url = 'FAILED' WHERE article_id = :article_id")
                session.execute(update_sql, {'article_id': article_id})
                session.commit()
            return
    else:
        try:
            logger.info(f"Processing article {article_id}, img_url: {img_url}")
            # 1. 下载图片
            response = requests.get(img_url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            content = response.content
        except Exception as e:
            logger.warning(f"Failed to download image for article {article_id}: {e}")
            # 下载失败，尝试使用默认图片
            if ensure_default_image_exists():
                try:
                    with open(DEFAULT_IMG_PATH, 'rb') as f:
                        content = f.read()
                except Exception as read_e:
                    logger.error(f"Failed to read default image for article {article_id}: {read_e}")
                    with std_db._scoped_session() as session:
                        update_sql = text(f"UPDATE {table_name} SET obs_url = 'FAILED' WHERE article_id = :article_id")
                        session.execute(update_sql, {'article_id': article_id})
                        session.commit()
                    return
            else:
                # 标记为失败
                with std_db._scoped_session() as session:
                    update_sql = text(f"UPDATE {table_name} SET obs_url = 'FAILED' WHERE article_id = :article_id")
                    session.execute(update_sql, {'article_id': article_id})
                    session.commit()
                return

    try:
        # 2. 准备临时文件
        # 如果是默认图片，可能需要特定的后缀，这里简单处理，默认 .jpg
        file_ext = ".jpg"
        if img_url and img_url.startswith('http'):
             original_filename = get_filename_from_url(img_url)
             ext = os.path.splitext(original_filename)[1]
             if ext and len(ext) <= 5:
                 file_ext = ext
        
        # 使用 article_id 生成 OBS 文件名
        obs_filename = f"{article_id}{file_ext}"
        obs_key = f"crawl_data/images/{obs_filename}"
        
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name
            
            # 3. 上传到 OBS
            obs_client.upload_bucket_file(obs_key, tmp_path)
            
            # 4. 构建 OBS URL
            # 构造 obs:// 协议 URL
            obs_url = f"obs://{settings.OBS_BUCKET_NAME}/{obs_key}"
            
            # 5. 更新数据库
            with std_db._scoped_session() as session:
                update_sql = text(f"UPDATE {table_name} SET obs_url = :obs_url WHERE article_id = :article_id")
                session.execute(update_sql, {'obs_url': obs_url, 'article_id': article_id})
                session.commit()
            
            logger.info(f"Successfully processed article {article_id}. OBS URL: {obs_url}")
            
        except Exception as e:
            logger.error(f"Error uploading/updating for article {article_id}: {e}")
            # 如果是上传失败，也可以标记为 FAILED，或者保留 NULL 下次重试
            pass
        finally:
            # 清理临时文件
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {tmp_path}: {e}")

    except Exception as e:
        logger.error(f"Unexpected error processing article {article_id}: {e}")

def process_obs_images(max_workers=15):
    """
    实时检查数据库中 obs_url 为空的记录，下载 img_parse_url 指向的图片并上传到 OBS，
    最后更新 obs_url 字段。
    """
    table_name = settings.CRAWL_TABLE_NAME
    
    logger.info(f"Starting OBS image processing service with {max_workers} workers...")
    
    while True:
        try:
            rows = []
            # 使用新的 session 获取待处理数据
            with std_db._scoped_session() as session:
                # 查询 obs_url 为空且 img_parse_url 不为空的记录
                # 排除掉已经标记为失败的记录 (obs_url = 'FAILED')
                query = text(f"""
                    SELECT article_id, img_parse_url 
                    FROM {table_name} 
                    WHERE (obs_url IS NULL OR obs_url = '' OR obs_url = 'FAILED') 
                    AND img_parse_url IS NOT NULL 
                    AND img_parse_url != ''
                    LIMIT 100
                """)
                
                result = session.execute(query)
                rows = result.fetchall()
                
            if not rows:
                logger.info("No pending records found. Sleeping for 60 seconds...")
                time.sleep(60)
                continue
            
            logger.info(f"Found {len(rows)} records to process.")
            
            # 使用线程池并发处理
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(process_single_article, rows)

        except Exception as e:
            logger.error(f"Database connection error or main loop error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    process_obs_images()
