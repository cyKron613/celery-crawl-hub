import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class ArticleParser:
    def __init__(self):
        # 请求头配置
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        self.timeout = 10  # 请求超时时间
        self.max_retries = 3  # 最大重试次数

        # 解析器映射
        self.parsers = {
            'mp.weixin.qq.com': self.parse_wechat_article,
            'default': self.parse_general_article
        }

    def fetch_with_retry(self, url):
        """带重试机制的请求方法"""
        for i in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                return response
            except Exception as e:
                if i == self.max_retries - 1:
                    raise
                print(f"Retrying ({i + 1}/{self.max_retries})...")
                time.sleep(2 * (i + 1))
        raise Exception("Max retries exceeded")

    def get_domain(self, url):
        """获取URL的域名"""
        try:
            return urlparse(url).hostname
        except:
            return 'unknown'

    def should_skip_text(self, text):
        """判断是否需要跳过某段文本"""
        skip_patterns = [
            re.compile(r'^[\s\n]*$'),
            re.compile(r'^图片$'),
            re.compile(r'^image$', re.I),
            re.compile(r'图片来源|图源|source|版权|编辑'),
            re.compile(r'^\s*[（(]?来源'),
            re.compile(r'^https?://'),
            re.compile(r'^[0-9a-zA-Z\s]{1,10}$'),
            re.compile(r'^[\u4e00-\u9fa5]{1,2}$'),
            re.compile(r'^微信号|^公众号|^扫码关注|^长按识别'),
            re.compile(r'^[0-9\s\-:：]+$'),
            re.compile(r'^[▲│●■◆※☆★⊙○⭐]'),
            re.compile(r'精选|推荐|置顶|广告|分享|点击'),
            re.compile(r'^预览时标签不可点'),
            re.compile(r'^轻触阅读原文'),
            re.compile(r'^继续滑动看下一个'),
            re.compile(r'^使用小程序'),
            re.compile(r'^取消\s*允许'),
            re.compile(r'^[×]?\s*分析'),
            re.compile(r'^[\-—]{3,}$'),
            re.compile(r'^点击收听'),
            re.compile(r'^Vessel Value'),
            re.compile(r'^[\u4e00-\u9fa5]{0,2}早知道$')
        ]
        return any(pattern.search(text) for pattern in skip_patterns)

    def clean_text(self, text):
        """清理文本"""
        return re.sub(r'[\s\u200b]+', ' ', text).strip()

    def remove_duplicates(self, content_list):
        """去除重复内容"""
        seen = set()
        unique_content = []
        for item in content_list:
            if item not in seen:
                seen.add(item)
                unique_content.append(item)
        return unique_content

    def parse_wechat_article(self, url):
        """解析微信公众号文章"""
        try:
            response = self.fetch_with_retry(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取标题
            title = soup.find(id='activity-name') or soup.find(class_='rich_media_title')
            # 提取作者
            author = soup.find(id='js_name') or soup.find(class_='rich_media_meta_nickname')

            # 提取内容区域
            content_div = soup.find(id='js_content')

            if not content_div:
                raise Exception("找不到文章内容区域")

            # 预处理内容
            for element in content_div.find_all(['a', 'img', 'iframe', 'video', 'audio', 'svg']):
                element.decompose()

            # 提取段落
            content = []
            current_section = 'default'
            sections = {}

            for element in content_div.find_all(['p', 'section', 'div']):
                text = element.get_text().strip()
                if not text:
                    continue

                # 检查标题
                is_bold = bool(element.find('strong')) or text.startswith('**')
                text = self.clean_text(text.replace('**', ''))

                if is_bold and len(text) < 30:
                    current_section = text
                    sections.setdefault(current_section, [])
                    continue

                if not self.should_skip_text(text) and len(text) >= 2:
                    sections.setdefault(current_section, []).append(text)

            # 合并内容
            for section, texts in sections.items():
                if texts:
                    if section != 'default':
                        content.append(f"【{section}】")
                    content.extend(texts)

            # 去重
            content = self.remove_duplicates(content)
            contents = '\n'.join(content)

            return {
                'title': title.get_text().strip() if title else '无标题',
                'author': author.get_text().strip() if author else '未知作者',
                'publish_time': self.find_publish_time(soup),
                'content': contents
            }
        except Exception as e:
            raise Exception(f"解析微信文章失败: {str(e)}")

    def parse_general_article(self, url):
        """解析通用网页文章"""
        try:
            response = self.fetch_with_retry(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 移除干扰元素
            for element in soup.find_all(['script', 'style', 'iframe', 'img', 'video', 'audio',
                                        'svg', 'footer', 'header', 'nav', 'ad']):
                element.decompose()

            # 查找标题
            title_selectors = [
                'h1', 'h2.title', '.article-title', '.post-title',
                '.entry-title', '.title', '#title', 'header h1',
                'article h1', '.main-title', '.content-title'
            ]
            title = next((t.get_text().strip() for selector in title_selectors
                         for t in soup.select(selector) if t.get_text().strip()), '无标题')

            # 查找正文
            content_selectors = [
                'article', '.article', '.post', '.entry', '.content',
                '#content', '.article-content', '.post-content',
                '.entry-content', '.main-content', '.article-body', '.main', '#main'
            ]
            content_container = max(
                (soup.select_one(selector) for selector in content_selectors),
                key=lambda x: len(x.get_text()) if x else 0,
                default=None
            )

            if not content_container:
                raise Exception("找不到内容区域")

            # 提取段落
            paragraphs = []
            for element in content_container.find_all(['p', 'div', 'section']):
                text = self.clean_text(element.get_text())
                if text and not self.should_skip_text(text) and len(text) >= 10:
                    paragraphs.append(text)

            # 去重
            paragraphs = self.remove_duplicates(paragraphs)
            contents = '\n'.join(paragraphs)

            return {
                'title': title,
                'author': self.find_author(soup),
                'publish_time': self.find_publish_time(soup),
                'content': contents
            }
        except Exception as e:
            raise Exception(f"解析通用文章失败: {str(e)}")

    def find_author(self, soup):
        """查找作者信息"""
        author_selectors = [
            '[class*="author"]', '[rel="author"]', '.writer',
            '.reporter', '.editor', '[class*="byline"]'
        ]
        for selector in author_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()
        return '未知作者'

    def find_publish_time(self, soup):
        """查找发布时间"""
        # 查找其他时间元素
        time_selectors = [
            'time', '[class*="time"]', '[class*="date"]',
            'meta[property="article:published_time"]', '[datetime]'
        ]
        for selector in time_selectors:
            element = soup.select_one(selector)
            if element:
                if element.has_attr('datetime'):
                    return element['datetime']
                if element.has_attr('content'):
                    return element['content']
                text = element.get_text().strip()
                if text:
                    return text
        return '未知时间'

    def parse_article(self, url):
        """解析文章入口方法"""
        domain = self.get_domain(url)
        parser = self.parsers.get(domain, self.parsers['default'])
        result = parser(url)

        # 添加统计信息
        result['stats'] = {
            'total_paragraphs': len(result['content']),
            'total_characters': sum(len(p) for p in result['content'])
        }

        return result

if __name__ == '__main__':
    # 实例化工具类
    parser = ArticleParser()

    # 解析文章
    url = "https://mp.weixin.qq.com/s?__biz=MzI1MjY2ODkyMw==&mid=2247486958&idx=1&sn=c5f326079a3f848c31d6e5fd47c336d1&chksm=e9e1737ade96fa6cddff18f9aef3cf812dc5097923273b63e614f9953079f813d80fff59ebe4#rd"
    try:
        result = parser.parse_article(url)
        print("标题:", result['title'])
        print("作者:", result['author'])
        print("内容:", result['content'])
        print("统计信息:", result['stats'])
        print("发布时间:", result['publish_time'])
    except Exception as e:
        print("解析失败:", str(e))