---
name: news-crawl-task-implementation
description: 为本 Celery 新闻项目实现或修改爬虫任务。涉及任务模块新增/修复/重构/重跑/更新，以及 Celery 路由、beat 调度、入库链路时触发本技能。优先复用已有任务模式，再以最小改动补丁落地。当用户要求"创建爬虫模板"、"生成爬虫代码"、"新增来源爬虫"时，必须同时生成 SQL 插入语句和 Python 模板代码。
---

# 新闻任务实现

## 目标
将提取方案转为可运行代码，并保证路由与调度一致。**每次新增爬虫必须同时生成 SQL 和 Python 模板两份产出物。**

## 双产出物要求

### 1. SQL 插入语句
- 文件位置：`sql/{source_name}_news.sql`
- 插入 `sdc_test.crawler_tasks` 表
- 包含所有 XPath 配置、调度参数、`custom_methods`（如需覆写方法）

### 2. Python 模板代码
- 文件位置：`sql/{source_name}_template.py`
- 继承 `XPathCrawlerTaskBase`（从 `src.utils.xpath_crawler_base` 导入）
- 类属性与 SQL 中的字段一一对应
- 如需覆写方法（如 `fetch_home_page`、`build_res_record`），在类中直接定义
- 模板可被 `template_parser.py` 解析，提取 attributes + custom_methods

### Python 模板结构示例
```python
from src.utils.xpath_crawler_base import XPathCrawlerTaskBase

class MyCrawlerTask(XPathCrawlerTaskBase):
    source_name = "example-news"
    prefix = "https://example.com"
    home_url_list = ["https://example.com/news"]
    url_xpath = "//article//a/@href"
    title_xpath = "//h1[@class='title']/text()"
    content_xpath = "//div[@class='content']//p/text()"
    date_xpath = "//time/@datetime"
    detail_wait_xpath = "//h1[@class='title']"
    
    # 如需覆写方法
    def fetch_home_page(self, home_url):
        # 自定义首页抓取逻辑（如需要点击 Tab）
        pass
```

## 步骤
1. 选择任务落点：
   - `src/main/tasks/time_tasks/`：高频通用任务
   - `src/main/tasks/new_tasks/`：新接入来源
   - `src/main/tasks/secondary_tasks/`：二级来源任务
2. 优先复用 `XPathCrawlerTaskBase`，仅在必要时覆写。
3. 校验 Celery 更新：
   - `src/settings/celery_config/celery_app.py` 中的 `task_routes`
   - 需要周期触发时同步更新 `beat_schedule`
4. 保证模块路径与路由字符串完全一致。
5. 提供可执行验证与最小回归检查。
6. 若需求包含正文图片占位：
   - 在正文提取中保留 DOM 顺序，避免 `//text()` 造成图片位置信息丢失。
   - 正文内图片使用 Markdown 占位：`![图片{index}]({url})`。
   - 图片链接使用归一化后的公网 URL，不新增 OSS/OBS 上传逻辑。

## 必查清单
- 任务入口函数名为 `time_task`
- 队列路由指向 `crawler_queue` 或需求指定队列
- 日期解析不会意外截断到午夜
- 可选字段缺失时仍保留有效 URL 记录
- 正文图片占位后，`detail_contents`/`detail_contents_cn` 仍为字符串且可直接渲染
- **SQL 和 Python 模板字段一致性**：两份产出物的 XPath、调度参数必须完全对齐

## 输出
- 变更文件列表（含 SQL 和 Python 模板）
- 每个变更的原因
- 验证结果与残余风险
