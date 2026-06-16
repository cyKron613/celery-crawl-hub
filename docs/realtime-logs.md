# 实时日志流功能

## 功能概述

实时日志流功能允许你在任务中心实时查看 Celery Worker 的执行日志。
通过 `docker logs --follow` 直接读取 Worker 容器的 stdout 日志，经 WebSocket 推送到前端。

## 架构设计

```
┌──────────────────────────┐
│  Celery Worker 容器       │
│  loguru → stdout          │
└──────────┬───────────────┘
           │ docker logs --follow
           ▼
┌──────────────────────────┐
│  FastAPI (crawler-api)    │
│  /api/ws/logs  WebSocket  │
│  挂载 /var/run/docker.sock │
└──────────┬───────────────┘
           │ WebSocket
           ▼
┌──────────────────────────┐
│  React 前端               │
│  LogViewer 组件           │
└──────────────────────────┘
```

## 核心组件

### 1. WebSocket 端点
**文件**: `src/main/api/logs/logs_router.py`

- 端点: `ws://host/api/ws/logs`
- 支持 query 参数: `?tail=N`（默认 100，历史日志行数）
- 通过 `asyncio.create_subprocess_exec("docker", "logs", "--follow", ...)` 流式读取 Worker 容器日志
- 自动解析 loguru 格式（时间戳 + 级别 + 消息），清理 ANSI 转义码和 Docker 时间戳前缀

### 2. Loguru 配置
**文件**: `src/main/config/handler/loguru_handler.py`

- `colorize=False`：避免 ANSI 转义码污染 docker logs 输出
- `enqueue` 已移除：Celery prefork 模式下不兼容
- 格式: `YYYY-MM-DD HH:mm:ss.SSS | LEVEL | process:thread | message`

### 3. 前端组件
**文件**: `web/src/components/LogViewer.tsx`

- 实时日志显示，支持自动滚动
- 日志级别颜色区分（ERROR/WARNING/INFO/DEBUG）
- 连接状态指示器
- 清空日志功能

## Docker 部署配置

### docker-compose.yml

`crawler-api` 服务需要挂载 Docker socket：

```yaml
crawler-api:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
```

### BaseDockerfile

基础镜像需要安装 Docker CLI：

```dockerfile
RUN apt-get install -y --no-install-recommends docker.io
```

## 使用方法

1. 打开任务中心 Web 界面
2. 点击左侧导航栏的「实时日志」
3. 执行爬虫任务，日志将实时显示

## 日志格式

每条日志包含：
- **时间戳**: `YYYY-MM-DDTHH:MM:SS.mmm` 格式
- **级别**: ERROR / WARNING / INFO / DEBUG
- **消息**: 日志内容

示例：
```
2026-06-16T01:41:54.713 | INFO | 🚀 开始执行爬虫任务: a1b2c3d4 (触发类型: manual)
2026-06-16T01:41:54.716 | INFO | crawler详情页处理成功: source=eworldship
2026-06-16T01:41:57.641 | INFO | Task crawler.execute_task[...] succeeded in 16.67s
```

## 故障排查

### 日志不显示

1. 确认 `crawler-api` 容器已挂载 `/var/run/docker.sock`
2. 确认基础镜像已安装 `docker.io`（docker CLI）
3. 检查 Worker 容器名称是否为 `docker-crawler-celery-worker-1`

### WebSocket 连接失败

1. 确认 Nginx 配置包含 WebSocket 升级头：
   ```nginx
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   ```
2. 确认 Vite 开发代理配置了 `ws: true`

## 相关文件

| 文件 | 说明 |
| --- | --- |
| `src/main/api/logs/logs_router.py` | WebSocket 端点，docker logs 流式读取 |
| `src/main/config/handler/loguru_handler.py` | Loguru Worker 日志配置 |
| `src/main/tasks/crawler_tasks.py` | Celery 任务执行 |
| `web/src/components/LogViewer.tsx` | 前端日志查看器 |
| `web/src/App.tsx` | 集成到任务中心 |
| `deploy/docker/docker-compose.yml` | Docker socket 挂载 |
| `deploy/docker/BaseDockerfile` | Docker CLI 安装 |

## 依赖

- `docker.io` (系统包) - Docker CLI，用于 `docker logs` 命令
- `loguru` (Python) - 日志框架
- `fastapi` (Python) - WebSocket 支持
- React (TypeScript) - 前端框架
