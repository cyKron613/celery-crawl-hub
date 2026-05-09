#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
import os
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import argparse
from fake_useragent import UserAgent
import dotenv



import pathlib
import sys

ROOT_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(ROOT_DIR))
# from src.utils.wechat_login import quick_login
from src.utils.craw_tools import get_primary_key, insert_into_table
from src.utils.ai_tools import match_web_url_class_label




# 加载环境变量
dotenv.load_dotenv()



# 初始化UserAgent对象
user_agent = UserAgent()

# 输出目录
OUTPUT_DIR = os.path.join(os.getcwd(), 'wechat_articles')


def get_random_headers():
    """获取随机的请求头"""
    # 将字典格式的cookie转换为字符串格式
    secret_file = os.path.join(os.getcwd(), 'wechat_cache.json')

    if os.path.exists(secret_file):
        secret_json = json.load(open(secret_file, 'r', encoding='utf-8'))
    else:
        secret_json = {}

    # 请在这里填入你的token和cookie
    COOKIE = secret_json.get('cookies') if secret_json else os.getenv('WECHAT_COOKIE')

    cookie_str = ""
    if isinstance(COOKIE, dict):
        cookie_str = '; '.join([f"{key}={value}" for key, value in COOKIE.items()])
    else:
        cookie_str = str(COOKIE) if COOKIE else ""
    
    return {
        "Host": "mp.weixin.qq.com",
        "User-Agent": user_agent.random,
        'cookie': cookie_str,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://mp.weixin.qq.com/'
    }

def search_account(account_name):
    """搜索公众号，获取fakeid"""
    print(f"正在搜索公众号: {account_name}")
    secret_file = os.path.join(os.getcwd(), 'wechat_cache.json')
    if os.path.exists(secret_file):
        secret_json = json.load(open(secret_file, 'r', encoding='utf-8'))
    else:
        secret_json = {}
    TOKEN = secret_json.get('token') if secret_json else os.getenv('WECHAT_TOKEN')


    url = 'https://mp.weixin.qq.com/cgi-bin/searchbiz'
    params = {
        'action': 'search_biz',
        'scene': 1,
        'begin': 0,
        'count': 10,
        'query': account_name,
        'token': TOKEN,
        'lang': 'zh_CN',
        'f': 'json',
        'ajax': '1',
    }

    try:
        response = requests.get(url, headers=get_random_headers(), params=params)
        data = response.json()

        if 'list' not in data:
            return f"搜索失败: {data.get('base_resp', {}).get('err_msg', '未知错误')}"

        accounts = []
        for item in data['list'][:3]:
            accounts.append({
                'name': item['nickname'],
                'fakeid': item['fakeid']
            })

        print('搜索到相关公众号：')
        for i, account in enumerate(accounts):
            print(f"  {i + 1}. {account['name']}")

        return accounts

    except Exception as e:
        raise Exception(status_code=500, content=f"搜索公众号出错: {e}")

def get_articles_list(fakeid, account_name, max_articles=10):
    """获取公众号文章列表"""
    print(f"正在获取 {account_name} 的文章列表（目标：{max_articles}篇）...")

    url = 'https://mp.weixin.qq.com/cgi-bin/appmsg'
    articles = []
    page = 0
    finished = False

    secret_file = os.path.join(os.getcwd(), 'wechat_cache.json')
    if os.path.exists(secret_file):
        secret_json = json.load(open(secret_file, 'r', encoding='utf-8'))
    else:
        secret_json = {}
    TOKEN = secret_json.get('token') if secret_json else os.getenv('WECHAT_TOKEN')

    while len(articles) < max_articles and not finished:
        params = {
            'action': 'list_ex',
            'begin': page * 5,
            'count': '5',
            'fakeid': fakeid,
            'type': '9',
            'query': '',
            'token': TOKEN,
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': '1',
        }

        try:
            time.sleep(random.uniform(3, 5))
            response = requests.get(url, headers=get_random_headers(), params=params)
            data = response.json()
            
            if 'base_resp' in data and data['base_resp'].get('error_msg'):
                print(data['base_resp']['error_msg'])
                time.sleep(60)
                continue
                
            if 'app_msg_list' not in data or not data['app_msg_list']:
                print(f"获取文章列表失败: {data.get('base_resp', {}).get('err_msg', '未知错误')}")
                break

            for article in data['app_msg_list']:
                if len(articles) >= max_articles:
                    finished = True
                    print(f"文章数量达到 {max_articles} 篇，结束搜索")
                    break

                # 添加文章信息
                articles.append({
                    'account_name': account_name,
                    'title': article['title'],
                    'link': article['link'],
                    'digest': article.get('digest', ''),
                    'publish_time': datetime.fromtimestamp(article['update_time']).strftime('%Y-%m-%d %H:%M:%S'),
                    'publish_timestamp': article['update_time']
                })
                print(f'添加文章：{len(articles)} {article["title"]}')

            page += 1

        except Exception as e:
            print(f"获取出错: {e}")
            break

    print(f"获取到 {len(articles)} 篇文章")
    return articles

def get_article_content(url, max_retries=3):
    """获取文章内容"""
    for retry in range(max_retries):
        try:
            headers = {
                "Host": "mp.weixin.qq.com",
                "User-Agent": user_agent.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://mp.weixin.qq.com/'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            for selector in ['#js_content', '.rich_media_content', '#activity-detail']:
                element = soup.find(id=selector[1:]) if selector.startswith('#') else soup.find(class_=selector[1:])
                if element:
                    return convert_to_markdown(element)
            return "未找到文章内容区域"

        except:
            if retry < max_retries - 1:
                time.sleep(3)
    return "获取内容失败"

def get_structured_article_data(url, max_retries=3):
    """获取文章结构化数据，包含标题、内容、日期、图片等信息"""
    for retry in range(max_retries):
        try:
            headers = {
                "Host": "mp.weixin.qq.com",
                "User-Agent": user_agent.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://mp.weixin.qq.com/'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            # 获取文章标题
            title_element = soup.find('h1') or soup.find('h2') or soup.find(class_='rich_media_title')
            article_title = title_element.get_text().strip() if title_element else ""

            # 获取文章内容区域
            content_element = None
            for selector in ['#js_content', '.rich_media_content', '#activity-detail']:
                element = soup.find(id=selector[1:]) if selector.startswith('#') else soup.find(class_=selector[1:])
                if element:
                    content_element = element
                    break

            if not content_element:
                return {
                    "article_title": article_title,
                    "article_content": "未找到文章内容区域",
                    "article_date": "",
                    "article_images": [],
                    "article_url": url
                }

            # 提取文章内容（正文 + 引用）
            content_text = extract_article_content(content_element)
            
            # 提取图片信息
            images = extract_article_images(content_element)
            
            # 提取发布日期
            date_element = soup.find('em', id='publish_time') or soup.find(class_='rich_media_meta rich_media_meta_text')
            article_date = date_element.get_text().strip() if date_element else ""

            return {
                "article_title": article_title,
                "article_content": content_text,
                "article_date": article_date,
                "article_images": images,
                "article_url": url
            }

        except Exception as e:
            print(f"获取结构化数据出错: {e}")
            if retry < max_retries - 1:
                time.sleep(3)
    
    return {
        "article_title": "",
        "article_content": "获取内容失败",
        "article_date": "",
        "article_images": [],
        "article_url": url
    }

def extract_article_content(element):
    """提取文章内容（正文 + 引用）"""
    if not element:
        return ""
    
    content_parts = []
    
    # 提取所有段落和文本内容
    for tag in element.find_all(['p', 'div', 'span', 'section']):
        text = tag.get_text().strip()
        if text and len(text) > 0:
            content_parts.append(text)
    
    # 提取引用内容
    for blockquote in element.find_all('blockquote'):
        quote_text = blockquote.get_text().strip()
        if quote_text:
            content_parts.append(f"引用：{quote_text}")
    
    # 合并内容，去除重复
    unique_content = []
    seen_content = set()
    
    for part in content_parts:
        if part not in seen_content:
            unique_content.append(part)
            seen_content.add(part)
    
    return '\n\n'.join(unique_content)

def extract_article_images(element):
    """提取文章中的图片信息"""
    if not element:
        return []
    
    images = []
    
    for img in element.find_all('img'):
        img_src = img.get('data-src') or img.get('src') or img.get('data-original')
        if img_src and img_src.startswith('http'):
            alt_text = img.get('alt', 'image')
            images.append({
                "img_url": img_src,
                "alt_text": alt_text
            })
    
    return images

def convert_to_markdown(element):
    """将HTML元素转换为Markdown格式"""
    if not element:
        return ""

    markdown_lines = []
    processed_texts = set()  # 用于去重

    # 处理标题
    for i in range(1, 7):
        for h in element.find_all(f'h{i}'):
            text = h.get_text().strip()
            if text and text not in processed_texts:
                markdown_lines.append(f'{"#" * i} {text}\n')
                processed_texts.add(text)

    # 处理段落和图片
    for tag in element.find_all(['p', 'div', 'section', 'img']):
        if tag.name == 'img':
            img_src = tag.get('data-src') or tag.get('src') or tag.get('data-original')
            if img_src and img_src.startswith('http'):
                alt_text = tag.get('alt', 'image')
                markdown_lines.append(f'![{alt_text}]({img_src})\n')
        else:
            text = tag.get_text().strip()
            # 去重逻辑：只添加未处理过的文本
            if text and len(text) > 5 and text not in processed_texts:
                markdown_lines.append(f'{text}\n')
                processed_texts.add(text)

    # 处理列表
    for ul in element.find_all(['ul', 'ol']):
        for i, li in enumerate(ul.find_all('li'), 1):
            text = li.get_text().strip()
            if text and text not in processed_texts:
                prefix = f'{i}. ' if ul.name == 'ol' else '- '
                markdown_lines.append(f'{prefix}{text}\n')
                processed_texts.add(text)

    # 处理引用
    for blockquote in element.find_all('blockquote'):
        text = blockquote.get_text().strip()
        if text and text not in processed_texts:
            for line in text.split('\n'):
                line_text = line.strip()
                if line_text and line_text not in processed_texts:
                    markdown_lines.append(f'> {line_text}\n')
                    processed_texts.add(line_text)

    # 如果没有结构化内容，返回纯文本
    if not markdown_lines:
        return element.get_text().strip()

    # 清理多余的空行
    result = ''.join(markdown_lines).strip()
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)

    return result

def clean_filename(title):
    """清理文件名，移除不合法的字符"""
    filename = re.sub(r'[<>:"/\\|?*]', '', title)
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename[:80] if len(filename) > 80 else filename or "无标题文章"

def save_single_article(article, account_name):
    """保存单篇文章为markdown文件"""
    save_dir = os.path.join(OUTPUT_DIR, clean_filename(account_name))
    os.makedirs(save_dir, exist_ok=True)

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{clean_filename(article['title'])}.md"
    filepath = os.path.join(save_dir, filename)

    markdown_content = f"""# {article['title']}

    **公众号**: {account_name}  
    **发布时间**: {article['publish_time']}  
    **原文链接**: {article['link']}  

    ---

    {article['content'] if article['content'] and article['content'] not in ["未获取", "获取内容失败"] else ""}"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"已保存: {filename}")
    return True

def wechat_crawler_main(
    account_name,
    max_articles=5,
    structured=False,
    db_insert=False,
    whole_article=False
):
    try:
        """主函数"""
        if whole_article:
            account_name_list = [
                "中国船级社CCS",
                "中国船舶工业行业协会",
                "数智前沿洞察 techInsight+",
                "科技日报",
                "海事早知道",
                "天翼智库",
                "中移智库",
                "量子位",
                "液态阳光",
                "信德海事 绿色航运",
                "环球零碳",
                "IMO工作机制",
                "环球科学",
                "碳索绿色未来",
                "双碳情报",
                "DNV船级社",
                "DNV能源",
                "DNV数字化服务",
                "满航 Manifold Times",
                "太铭航运",
                "中国船检",
                "ABS美国船级社",
                "RINA意大利船级社",
                "韩国船级社",
                "ClassNK日本船级社",
                "法国BV船级社",
                "LR劳氏船级社",
                "中国船舶集团上海船舶研究设计院",
                "海洋装备战略研究院",
                "全球甲醇行业协会MI",
                "知领",
                "中国信通院CAICT",
                "船事探索",
                "碳中和圈子",
                "经济参考报",
                "战略前沿技术",
                "清洁交通伙伴关系",
                "电船纪元",
                "中国科技信息",
                "船舶先进制造技术",
                "信创纵横",
                "新基建创新研究院",
                "文景信息WinJoinIT",
                "灵碳星球",
                "洲际船务",
                "生物燃料与生物基化学品",
                "国家智能制造专家委员会",
                "数据驱动智能"
            ]
        else:
            account_name_list = [account_name]

        total_results = []
        for account_name in account_name_list:
            try:
                print(f"开始爬取公众号: {account_name}")
                print(f"目标文章数量: {max_articles}")
                print(f"输出目录: {OUTPUT_DIR}")
                # 搜索公众号
                accounts = search_account(account_name)
                if not accounts:
                    return  f"未找到公众号: {account_name}"
                elif isinstance(accounts, str) and "搜索失败" in accounts:
                    return [{
                        "name": account_name,
                        "err_msg": accounts
                    }]
                
                # 使用第一个匹配的公众号
                selected_account = accounts[0]
                print(f"使用公众号: {selected_account['name']} (ID: {selected_account['fakeid']})")
                
                # 获取文章列表
                articles = get_articles_list(selected_account['fakeid'], selected_account['name'], max_articles)
                if not articles or len(articles) == 0:
                    print(f"{account_name} 未获取到文章")
                    continue
                
                print(f"\n开始获取 {len(articles)} 篇文章的内容...")
                saved_count = 0
                
                # 存储结构化数据结果
                structured_results = []
                
                # 获取并保存每篇文章
                for i, article in enumerate(articles, 1):
                    print(f"获取第 {i}/{len(articles)} 篇: {article['title']}")
                    
                    if structured:
                        # 获取结构化数据
                        structured_data = get_structured_article_data(article['link'])
                        structured_data['original_title'] = article['title']
                        structured_data['original_date'] = article['publish_time']
                        structured_results.append(structured_data)
                        print(f"结构化数据获取完成: {structured_data['article_title']}")
                    else:
                        # 获取文章内容
                        article['content'] = get_article_content(article['link'])
                        if save_single_article(article, account_name):
                            saved_count += 1
                    
                    # 添加延迟，避免请求过快
                    if i < len(articles):
                        time.sleep(random.uniform(2, 4))
                
                if structured:
                    # 返回结构化数据
                    print("\n结构化数据结果:")
                    for i, result in enumerate(structured_results, 1):
                        print(f"\n第 {i} 篇文章:")
                        print(f"标题: {result['article_title']}")
                        print(f"日期: {result['article_date']}")
                        print(f"URL: {result['article_url']}")
                        print(f"图片数量: {len(result['article_images'])}")
                        print(f"内容预览: {result['article_content'][:200]}...")
                    
                    db_results = []
                    for res in structured_results:
                        try:
                            img_url = res["article_images"][0].get("img_url")
                        except IndexError:
                            img_url = 'https://ai-doc.data.myvessel.cn/news/%E8%88%AA%E8%BF%90%E5%BF%AB%E8%AE%AF%E5%A4%B4%E5%9B%BE.jpg?OSSAccessKeyId=LTAI5t7nfdMfD7YeTFpAENJ4&Expires=2725518616&Signature=Tw08oPC0RL%2FKweHU1Q1NlJZhZHA%3D'

                        db_result = {
                            "img_parse_url": img_url,
                            "detail_url": res["article_url"],
                            "detail_title_cn": res["article_title"],
                            "detail_date": res["original_date"],
                            "detail_timestamptz": res["original_date"]+"+0800",
                            "detail_contents_cn": res["article_content"]
                        }

                        try:
                            article_id = get_primary_key("wechat_article", db_result)
                            db_result["article_id"] = article_id
                            from dateutil.tz import tzoffset
                            dt_utc8 = datetime.now().replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
                            db_result["update_time"] = str(dt_utc8.isoformat())
                            db_result["class_level_1"] = match_web_url_class_label(db_result["detail_title_cn"], db_result["detail_contents_cn"])
                            db_result["class_level_2"] = ""

                        except Exception as e:
                            print(f"{e}, {e.__traceback__.tb_lineno}")
                            raise

                        db_results.append(db_result)

                    if db_insert:
                        insert_into_table(db_results, account_name)

                    time.sleep(random.uniform(2, 4))

                    total_results.extend(db_results)

                else:
                    print(f"\n爬取完成！")
                    print(f"成功保存文章数: {saved_count}/{len(articles)}")
                    print(f"文件保存目录: {OUTPUT_DIR}")
                    return None
            except Exception as e:
                print(f"{e}, {e.__traceback__.tb_lineno}")
                continue

        return total_results

    except Exception as e:
        print(f"{e}, {e.__traceback__.tb_lineno}")
        raise
    

if __name__ == "__main__":
    account_name = input("请输入要爬取的公众号名称: ")
    max_articles = int(input("请输入要获取的文章数量: ") or "5")
    structured = input("是否获取结构化数据 (y/n): ").lower() == 'y'
    db_insert = input("是否插入数据库 (y/n): ").lower() == 'y'
    # whole_article = input("是否获取完整文章内容 (y/n): ").lower() == 'y'
    wechat_crawler_main(account_name, max_articles, structured, db_insert, False)
