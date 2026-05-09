# Celery Crawl Hub

Celery Crawl Hub 是一个基于 FastAPI、Celery、Redis、PostgreSQL 和 Playwright 的可配置低代码爬虫任务平台。它支持通过 API 或 Gradio 控制台管理爬虫任务、手动执行任务、按 interval/cron 调度任务，并记录任务执行结果。

## 功能特性

- **低代码爬虫配置**：通过 XPath、URL 列表、重试策略、内容长度过滤等字段定义采集规则。
- **任务管理 API**：提供任务创建、导入、更新、删除、执行、调度与结果查询接口。
- **异步任务调度**：基于 Celery worker 和 Celery beat 支持定时扫描与分发。
- **浏览器采集能力**：集成 Playwright，适合动态页面抓取场景。
- **数据库持久化**：任务、执行记录与采集结果可落 PostgreSQL / 兼容数据库。
- **Redis 支持**：用于 Celery broker/result backend，也可作为缓存组件。
- **Gradio 控制台**：提供基础可视化操作入口。
- **容器化部署**：内置 Dockerfile 和 Docker Compose 示例。

## 技术栈

- Python 3.12+
- FastAPI / Uvicorn
- Celery / Redis
- SQLAlchemy / asyncpg / psycopg2 / PyMySQL
- PostgreSQL
- Playwright
- Gradio

## 项目结构

```text
.
├── main.py                         # FastAPI 应用入口
├── gradio_app.py                   # Gradio 控制台入口
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板
├── deploy/
│   └── docker/                     # Dockerfile / Compose
├── docs/                           # API 文档
├── sql/                            # 初始化 SQL
└── src/
    ├── main/api/                   # FastAPI 路由
    ├── main/config/                # 配置、生命周期、中间件
    ├── main/models/                # ORM 模型
    ├── main/repository/            # 数据访问层
    ├── main/service/               # 业务服务
    ├── main/tasks/                 # Celery app 与任务
    └── utils/                      # 爬虫、数据库、OBS、AI 等工具
```

## 快速开始

### 1. 准备环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

然后按实际环境修改 `.env`。最少需要确认以下配置：

- `BACKEND_SERVER_HOST` / `BACKEND_SERVER_PORT`
- `DOCS_AUTH_USERNAME` / `DOCS_AUTH_PASSWORD`
- `POSTGRES_*`
- `POSTGRES_SCHEMA`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `PROD_REDIS_*` / `TEST_REDIS_*`

完整模板见 [.env.example](.env.example)。请勿提交真实 `.env` 文件。

### 2. 本地 Python 启动

安装依赖：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

初始化数据库表（三个业务表：`crawler_tasks`、`ex_crawl_log`、`ex_shipping_information`）：

```bash
psql "$DATABASE_URL" -f sql/init_all.sql
```

> 项目未集成 Alembic 等迁移工具，也不会在应用启动时自动 `create_all`，需手动执行上述 SQL。Docker Compose 启动时会自动加载 `sql/` 下的这三个脚本。

启动 API：

```bash
python main.py
```

启动 Celery worker：

```bash
celery -A src.main.tasks.celery_app:celery_app worker -Q celery -l info --pool=solo --concurrency=1
```

启动翻译/扩展队列 worker：

```bash
celery -A src.main.tasks.celery_app:celery_app worker -Q translate_schedule -l info --pool=solo --concurrency=1
```

启动 Celery beat：

```bash
celery -A src.main.tasks.celery_app:celery_app beat -l info
```

启动 Gradio 控制台：

```bash
python gradio_app.py
```

默认访问入口：

- API 登录页：`http://127.0.0.1:8000/login`
- API 文档：`http://127.0.0.1:8000/api-doc.html`
- Gradio 控制台：`http://127.0.0.1:7860`

## Docker Compose

Docker Compose 示例会启动 PostgreSQL、Redis、API、Celery worker 和 Celery beat。

部署被拆为**构建**与**运行**两步，避免 buildx 在容器化构建器下访问 Docker Hub 失败：

### 1) 构建镜像（一次性 / 代码变更后）

基础镜像内置阿里云镜像源、Python 依赖与 Playwright 浏览器，国内拉取友好。

```bash
# amd64
docker build -f deploy/docker/BaseDockerfile -t celery-crawl-hub:base .
# ARM64（如 Apple Silicon），二选一
# docker build -f deploy/docker/BaseDockerfile_arm64 -t celery-crawl-hub:base .

# 应用镜像（仅复制代码，秒级完成）
docker build -f deploy/docker/Dockerfile -t celery-crawl-hub:latest .
```

或者直接用 Makefile：

```bash
make base    # 仅首次或依赖变更时执行
make image   # 代码变更时执行
make build   # = base + image

# 后续快速部署
make image && make down && make up && make logs
```

### 2) 运行服务

```bash
cp .env.example .env
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.yml logs -f
```

或使用 Makefile：

```bash
make up
make logs
make down
```

> Compose 中把容器内数据库与 Redis 主机自动覆盖为 `postgres` / `redis`，本地 `.env` 仍可保留 `localhost` 便于非容器方式调试。
> Compose 不再触发构建（`pull_policy: never`），所以执行 `up` 前必须先 `make build` 或手动构建过镜像。

## API 文档

详细接口说明见 [docs/crawler-api.md](docs/crawler-api.md)。核心接口前缀：

```text
/api/v1/crawler
```

常见能力：

- 创建/导入任务
- 更新任务配置
- 查询任务列表与详情
- 手动执行任务
- 查询执行记录与采集结果
- 启用 interval / cron 调度

## 数据库初始化

项目提供三个 SQL 脚本，默认 schema 为 `sdc_test`，可通过 `POSTGRES_SCHEMA` 调整（需同步修改 SQL 文件中的 schema 名）：

| 文件 | 用途 |
|---|---|
| [sql/crawler_tasks.sql](sql/crawler_tasks.sql) | 任务与执行记录表 |
| [sql/ex_crawl_log.sql](sql/ex_crawl_log.sql) | 采集同步日志表 |
| [sql/ex_shipping_information.sql](sql/ex_shipping_information.sql) | 采集结果业务表 |
| [sql/init_all.sql](sql/init_all.sql) | 一键加载以上三个脚本 |

初始化方式：

- **Docker Compose**：首次启动时自动执行三个 SQL，无需手工处理。
- **本地裸跑**：运行 `psql "$DATABASE_URL" -f sql/init_all.sql`。

项目未集成 Alembic，应用启动不会自动创建表结构；后续表结构变更需手动维护 SQL。

## 环境变量说明

| 变量 | 说明 |
|---|---|
| `ENVIRONMENT` | 运行环境，`DEV` 或 `PROD` |
| `BACKEND_SERVER_HOST` | API 监听地址 |
| `BACKEND_SERVER_PORT` | API 监听端口 |
| `API_PREFIX` | API 路由前缀 |
| `DOCS_URL` / `OPENAPI_URL` / `REDOC_URL` | 文档路由 |
| `DOCS_AUTH_USERNAME` / `DOCS_AUTH_PASSWORD` | 文档登录凭据 |
| `CELERY_BROKER_URL` | Celery broker 地址 |
| `CELERY_RESULT_BACKEND` | Celery 结果后端地址 |
| `POSTGRES_*` | 主数据库连接配置 |
| `POSTGRES_*_ANOTHER` | 可选第二数据库连接配置 |
| `POSTGRES_SCHEMA` | 主数据库 schema |
| `PROD_REDIS_*` / `TEST_REDIS_*` | Redis 客户端配置 |
| `OPENAI_API_KEY` | 可选 AI 能力密钥 |
| `OBS_*` | 可选对象存储配置 |
| `GRADIO_*` | Gradio 控制台配置 |

## 开源安全说明

- 不要提交 `.env`、数据库密码、API Key、私有镜像仓库地址等敏感信息。
- 已提供 [.env.example](.env.example) 作为公开模板。
- 若历史提交曾包含敏感信息，开源前应轮换对应凭据，并清理 Git 历史。

## 开发建议

- 新增接口时同步更新 [docs/crawler-api.md](docs/crawler-api.md)。
- 新增环境变量时同步更新 [.env.example](.env.example) 和 README。
- 爬虫任务执行失败时优先检查 Celery worker 日志、数据库连接、Redis 连接与 Playwright 浏览器依赖。

## License

开源前请补充许可证文件，例如 MIT、Apache-2.0 或其他适合项目的许可证。
