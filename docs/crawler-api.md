# Crawler Studio API 文档

## 1. 基本信息

- 接口前缀: `/api/v1/crawler`
- 代码路由位置: `src/main/api/crawler/crawler_router.py`
- 主要用途: 爬虫任务的创建、更新、执行、调度和结果查询

## 2. 公共响应结构

所有接口均返回统一结构:

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| code | integer | 业务状态码(通常与 HTTP 状态一致) | 200 |
| message | string | 响应描述 | 获取成功 |
| data | object/array/null | 具体业务数据 | 见各接口示例 |

示例:

```json
{
  "code": 200,
  "message": "获取成功",
  "data": {}
}
```

---

## 3. 任务配置字段说明(创建/更新/导入共用)

> 对应 Schema: `CrawlerTaskCreateRequest` / `CrawlerTaskUpdateRequest`

| 字段 | 类型 | 是否必填 | 默认值 | 约束 | 说明 | 示例 |
|---|---|---|---|---|---|---|
| task_name | string | 是 | 无 | 非空 | 任务名称(唯一) | jmd-crawler-demo |
| description | string/null | 否 | null | - | 任务描述 | 日本海运新闻抓取 |
| source_name | string | 是 | 无 | 非空 | 来源标识 | jmd |
| prefix | string/null | 否 | null | - | URL 前缀 | https://www.jmd.co.jp |
| home_url_list | array[string] | 是 | 无 | 至少 1 项 | 首页 URL 列表 | ["https://www.jmd.co.jp/"] |
| url_xpath | string/array/null | 是 | 无 | - | 列表详情链接 XPath | //h3/a/@href |
| title_xpath | string/array/null | 是 | 无 | - | 标题 XPath | //h1/text() |
| content_xpath | string/array/null | 是 | 无 | - | 正文 XPath | //article//p//text() |
| home_date_xpath | string/array/null | 否 | null | - | 列表日期 XPath | //span[@class='date']/text() |
| date_xpath | string/array/null | 否 | null | - | 详情日期 XPath | //time/text() |
| image_xpath | string/array/null | 否 | null | - | 列表图片 XPath | //img/@src |
| detail_image_xpath | string/array/null | 否 | null | - | 详情图片 XPath | //article//img/@src |
| url_limit | integer | 否 | 10 | 1~200 | 单次抓取详情页数量 | 20 |
| list_retry_count | integer | 否 | 1 | 0~10 | 列表重试次数 | 2 |
| list_retry_sleep_seconds | integer | 否 | 3 | 0~60 | 列表重试间隔秒 | 3 |
| detail_retry_count | integer | 否 | 0 | 0~10 | 详情重试次数 | 2 |
| detail_retry_sleep_seconds | integer | 否 | 2 | 0~60 | 详情重试间隔秒 | 2 |
| min_content_length | integer | 是 | 无 | >=0 | 正文最小长度过滤 | 80 |
| max_content_length | integer | 是 | 无 | >=0 且为 0 或 >=min_content_length | 正文最大长度过滤，0 表示不限制 | 50000 |
| dedupe_urls | boolean | 否 | false | - | 是否对详情链接去重 | true |
| home_wait_xpath | string/array/null | 否 | null | - | 首页等待元素 XPath | //div[@id='list-ready'] |
| detail_wait_xpath | string/array/null | 否 | null | - | 详情等待元素 XPath | //article |
| source_language | string | 否 | auto | manual/auto语义由业务处理 | 来源语种 | ja |
| source_map | object | 否 | {} | key-value | 域名到来源中文名映射 | {"jmd.co.jp":"日本海运新闻社"} |
| content_joiner | string | 否 | " " | - | 正文拼接符 | " " |
| default_image_url | string/null | 否 | null | - | 默认图片 URL | https://example.com/default.jpg |
| date_patterns | array[string] | 否 | 内置列表 | - | 日期解析格式列表 | ["%Y/%m/%d", "%Y-%m-%d"] |
| schedule_type | string | 否 | manual | manual/interval/cron | 调度类型 | interval |
| cron_expression | string/null | 否 | null | schedule_type=cron 时必填 | Cron 表达式 | */30 * * * * |
| interval_seconds | integer/null | 否 | null | schedule_type=interval 时必填 且>=1 | 间隔秒数 | 1800 |
| schedule_enabled | boolean | 否 | false | manual 类型不可为 true | 是否启用调度 | true |

---

## 4. 接口明细

## 4.1 创建任务

- 方法: `POST`
- 路径: `/api/v1/crawler/tasks`

### 输入参数

| 位置 | 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| Body | 任务配置字段 | object | 是 | 见第 3 节 |

### 输入示例

```json
{
  "task_name": "jmd-crawler-demo",
  "description": "日本海运新闻社首页新闻抓取任务",
  "source_name": "jmd",
  "prefix": "https://www.jmd.co.jp",
  "home_url_list": ["https://www.jmd.co.jp/"],
  "url_xpath": "//section[@class='kiji-index--category']//h3//a/@href",
  "title_xpath": "//h1[@class='article--title']/text()",
  "content_xpath": "//article[@class='content']//p//text()[not(ancestor::script) and not(ancestor::style)]",
  "home_date_xpath": "//span[@class='text kiji-index--category--kiji_date']//text()",
  "date_xpath": null,
  "image_xpath": null,
  "detail_image_xpath": null,
  "url_limit": 10,
  "list_retry_count": 1,
  "list_retry_sleep_seconds": 3,
  "detail_retry_count": 2,
  "detail_retry_sleep_seconds": 1,
  "min_content_length": 0,
  "max_content_length": 0,
  "dedupe_urls": true,
  "home_wait_xpath": null,
  "detail_wait_xpath": null,
  "source_language": "ja",
  "source_map": {"jmd.co.jp": "日本海运新闻社（Japan Marine Daily）"},
  "content_joiner": " ",
  "default_image_url": null,
  "date_patterns": ["%Y/%m/%d", "%Y-%m-%d"],
  "schedule_type": "manual",
  "cron_expression": null,
  "interval_seconds": null,
  "schedule_enabled": false
}
```

### 输出示例(成功)

```json
{
  "code": 201,
  "message": "任务创建成功",
  "data": {
    "id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "task_name": "jmd-crawler-demo",
    "source_name": "jmd",
    "min_content_length": 0,
    "max_content_length": 0,
    "schedule_type": "manual",
    "schedule_enabled": false,
    "created_at": "2026-03-23T10:00:00+08:00",
    "updated_at": "2026-03-23T10:00:00+08:00"
  }
}
```

---

## 4.2 导入任务配置

- 方法: `POST`
- 路径: `/api/v1/crawler/tasks/import`
- 说明: 与创建接口字段、校验和返回结构一致

---

## 4.3 更新任务

- 方法: `PUT`
- 路径: `/api/v1/crawler/tasks/{task_id}`

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 默认值 | 说明 | 示例 |
|---|---|---|---|---|---|---|
| Path | task_id | string(UUID) | 是 | 无 | 任务 ID | d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01 |
| Body | 任务配置字段 | object | 是 | 无 | 见第 3 节 | 同创建 |

### 输出示例

```json
{
  "code": 200,
  "message": "任务更新成功",
  "data": {
    "id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "task_name": "jmd-crawler-demo",
    "schedule_type": "interval",
    "interval_seconds": 1800,
    "schedule_enabled": true
  }
}
```

---

## 4.4 获取任务列表

- 方法: `GET`
- 路径: `/api/v1/crawler/tasks`

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---|---|---|---|---|
| Query | page | integer | 否 | 1 | >=1 | 页码 |
| Query | page_size | integer | 否 | 20 | 1~200 | 每页条数 |

### 请求示例

`GET /api/v1/crawler/tasks?page=1&page_size=20`

### 输出示例

```json
{
  "code": 200,
  "message": "获取成功",
  "data": [
    {
      "id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
      "task_name": "jmd-crawler-demo",
      "source_name": "jmd",
      "last_status": "idle",
      "schedule_type": "manual",
      "schedule_enabled": false
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "total_pages": 1
}
```

---

## 4.5 获取任务详情

- 方法: `GET`
- 路径: `/api/v1/crawler/tasks/{task_id}`

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| Path | task_id | string(UUID) | 是 | 任务 ID |

### 输出示例

```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "task_name": "jmd-crawler-demo",
    "source_name": "jmd",
    "min_content_length": 0,
    "max_content_length": 0,
    "last_run_at": null,
    "last_status": "idle"
  }
}
```

---

## 4.6 删除任务

- 方法: `DELETE`
- 路径: `/api/v1/crawler/tasks/{task_id}`

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| Path | task_id | string(UUID) | 是 | 任务 ID |

### 输出示例

```json
{
  "code": 200,
  "message": "任务删除成功",
  "data": {
    "task_id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "deleted": true
  }
}
```

---

## 4.7 手动执行任务

- 方法: `POST`
- 路径: `/api/v1/crawler/tasks/{task_id}/run`

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| Path | task_id | string(UUID) | 是 | 任务 ID |

### 输出示例

```json
{
  "code": 200,
  "message": "任务已提交执行",
  "data": {
    "task_id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "celery_task_id": "6644ba9b-1720-4211-8dd5-9b4b93b9e776"
  }
}
```

---

## 4.8 开启调度

- 方法: `POST`
- 路径: `/api/v1/crawler/tasks/{task_id}/schedule/start`

### 输出示例

```json
{
  "code": 200,
  "message": "调度已启动",
  "data": {
    "task_id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "schedule_enabled": true,
    "next_run_at": "2026-03-23T10:30:00+08:00"
  }
}
```

---

## 4.9 暂停调度

- 方法: `POST`
- 路径: `/api/v1/crawler/tasks/{task_id}/schedule/pause`

### 输出示例

```json
{
  "code": 200,
  "message": "调度已暂停",
  "data": {
    "task_id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "schedule_enabled": false,
    "next_run_at": null
  }
}
```

---

## 4.10 获取任务执行记录

- 方法: `GET`
- 路径: `/api/v1/crawler/tasks/{task_id}/executions`

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---|---|---|---|---|
| Path | task_id | string(UUID) | 是 | 无 | - | 任务 ID |
| Query | limit | integer | 否 | 20 | 1~100 | 返回记录条数 |

### 输出示例

```json
{
  "code": 200,
  "message": "获取成功",
  "data": [
    {
      "id": "3f7f0d91-2f64-4b4e-b0f8-a77f0ebecb8e",
      "task_id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
      "trigger_type": "manual",
      "status": "success",
      "celery_task_id": "6644ba9b-1720-4211-8dd5-9b4b93b9e776",
      "started_at": "2026-03-23T10:31:00+08:00",
      "finished_at": "2026-03-23T10:32:11+08:00",
      "result_count": 12,
      "error_message": null
    }
  ]
}
```

---

## 4.11 根据 celery_task_id 获取执行结果

- 方法: `GET`
- 路径: `/api/v1/crawler/executions/{celery_task_id}/results`

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| Path | celery_task_id | string | 是 | Celery 任务 ID | 6644ba9b-1720-4211-8dd5-9b4b93b9e776 |

### 输出示例

```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "execution_id": "3f7f0d91-2f64-4b4e-b0f8-a77f0ebecb8e",
    "task_id": "d9a9bb7d-8d88-4f66-bf4f-2b9b9d1d8f01",
    "celery_task_id": "6644ba9b-1720-4211-8dd5-9b4b93b9e776",
    "status": "success",
    "error_message": null,
    "started_at": "2026-03-23T10:31:00+08:00",
    "finished_at": "2026-03-23T10:32:11+08:00",
    "result_count": 12,
    "inserted_article_ids": [
      "jmd_20260323_abcdef123456"
    ],
    "records": [
      {
        "article_id": "jmd_20260323_abcdef123456",
        "detail_url": "https://www.jmd.co.jp/articles/xxx",
        "detail_title": "sample title",
        "detail_contents": "sample content"
      }
    ]
  }
}
```

---

## 4.12 分页获取正式入库数据

- 方法: `GET`
- 路径: `/api/v1/crawler/inserted-data`
- 说明: 分页查询 `ex_shipping_information` 表内所有正式入库数据，默认按 `update_time`、`detail_date`、`article_id` 倒序展示。

### 参数说明

| 位置 | 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---|---|---|---|---|
| Query | page | integer | 否 | 1 | >=1 | 页码 |
| Query | page_size | integer | 否 | 20 | 1~200 | 每页条数 |

### 请求示例

`GET /api/v1/crawler/inserted-data?page=1&page_size=20`

### 输出示例

```json
{
  "code": 200,
  "message": "获取成功",
  "data": [
    {
      "article_id": "jmd_20260323_abcdef123456",
      "detail_url": "https://www.jmd.co.jp/articles/xxx",
      "detail_title": "sample title",
      "detail_date": "2026-03-23",
      "update_time": "2026-03-23T10:32:11+08:00",
      "news_source_name_cn": "日本海运新闻社",
      "detail_contents": "sample content"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "total_pages": 1
}
```

---

## 5. 常见错误响应示例

### 5.1 参数校验失败

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "max_content_length"],
      "msg": "max_content_length 不能小于 min_content_length",
      "input": 10
    }
  ]
}
```

### 5.2 任务不存在

```json
{
  "code": 404,
  "message": "任务不存在",
  "data": null
}
```

### 5.3 任务名称重复

```json
{
  "code": 400,
  "message": "任务名称已存在",
  "data": null
}
```
