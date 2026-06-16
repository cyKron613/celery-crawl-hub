# 实时日志流功能实现总结

## 实现日期
2026-06-15

## 功能概述
为任务中心添加了实时日志流功能，允许用户通过 WebSocket 实时查看 Celery Worker 的执行日志。

## 核心架构

```
Celery Worker → Loguru → Redis Pub/Sub → FastAPI WebSocket → React LogViewer
```

## 实现的文件

### 后端 (Python)

1. **`src/main/service/log_publisher.py`** (新建)
   - `RedisLogPublisher`: 单例模式的 Redis Pub/Sub 发布器
   - `create_loguru_redis_sink()`: 创建 loguru 的 Redis sink
   - 自动携带 task_id 上下文

2. **`src/main/api/logs/logs_router.py`** (新建)
   - WebSocket 端点: `/api/v1/ws/logs`
   - `ConnectionManager`: 管理 WebSocket 连接，支持按 task_id 过滤
   - 异步 Redis 监听器

3. **`src/main/api/logs/__init__.py`** (新建)
   - 导出 logs_router

4. **`src/main/config/handler/loguru_handler.py`** (修改)
   - 在 `configure_loguru_for_worker()` 中添加 Redis sink
   - 所有 Worker 日志自动发布到 Redis

5. **`src/main/tasks/crawler_tasks.py`** (修改)
   - 在 `_execute_crawler_task()` 开头绑定 task_id 上下文
   - 使用 `logger.bind(task_id=task_id)` 确保所有日志携带 task_id

6. **`src/main/api/endpoints.py`** (修改)
   - 注册 logs_router

### 前端 (TypeScript/React)

1. **`web/src/components/LogViewer.tsx`** (新建)
   - 实时日志显示组件
   - WebSocket 连接管理
   - 自动滚动、清空日志、连接状态指示
   - 日志级别颜色区分
   - 支持按 task_id 过滤

2. **`web/src/App.tsx`** (修改)
   - 添加 'logs' 面板类型
   - 在侧边栏添加「实时日志」导航按钮
   - 集成 LogViewer 组件到任务中心

### 文档

1. **`docs/realtime-logs.md`** (新建)
   - 完整的功能说明和使用指南
   - 架构设计和技术细节
   - 故障排查和扩展功能

## 技术亮点

### 1. 日志上下文绑定
使用 loguru 的 `bind()` 方法，在任务执行时自动绑定 task_id：
```python
task_logger_ctx = logger.bind(task_id=task_id, celery_task_id=celery_task_id)
```
所有后续日志自动携带 task_id，无需手动传递。

### 2. 按 task_id 过滤
- 后端：ConnectionManager 按 task_id 分组管理连接
- 前端：通过 WebSocket query 参数 `?task_id=xxx` 过滤
- 支持订阅全部日志（不传 task_id）

### 3. 优雅降级
- Redis 连接失败不影响爬虫执行
- WebSocket 断开自动重连
- 日志发布失败静默处理

### 4. 性能优化
- 使用 Redis Pub/Sub（低延迟）
- 异步处理，不阻塞主流程
- 前端自动滚动可关闭

## 使用方法

1. 启动服务：Redis、Celery Worker、FastAPI、React
2. 打开任务中心，点击「实时日志」
3. 选择任务（可选）以过滤日志
4. 执行爬虫任务，实时查看日志

## 日志格式示例

```
14:23:45.123 INFO     [a1b2c3d4] 🚀 开始执行爬虫任务: a1b2c3d4-e5f6-7890
14:23:45.456 INFO     [a1b2c3d4] 成功抓取 15 条数据
14:23:46.789 INFO     [a1b2c3d4] 任务执行完成
```

## 依赖项

- `redis` (Python)
- `redis.asyncio` (Python)
- `loguru` (Python)
- `fastapi` (Python)
- React (TypeScript)

## 测试建议

1. **单元测试**
   - 测试 RedisLogPublisher 的连接和发布
   - 测试 ConnectionManager 的连接管理
   - 测试日志过滤逻辑

2. **集成测试**
   - 启动完整服务，执行爬虫任务
   - 验证日志实时显示
   - 测试多客户端并发连接
   - 测试 task_id 过滤功能

3. **性能测试**
   - 高并发日志场景
   - 大量 WebSocket 连接
   - 长时间运行稳定性

## 后续优化建议

1. **日志持久化**
   - 将日志写入数据库或文件系统
   - 支持历史日志查询

2. **日志级别过滤**
   - 前端添加级别选择器
   - 只显示 ERROR/WARNING/INFO

3. **日志搜索**
   - 添加搜索框
   - 支持关键词高亮

4. **日志导出**
   - 导出为 TXT/JSON 格式
   - 支持时间范围选择

5. **日志告警**
   - ERROR 级别日志触发告警
   - 集成邮件/钉钉通知

## 相关文件清单

```
src/main/service/log_publisher.py
src/main/api/logs/logs_router.py
src/main/api/logs/__init__.py
src/main/config/handler/loguru_handler.py
src/main/tasks/crawler_tasks.py
src/main/api/endpoints.py
web/src/components/LogViewer.tsx
web/src/App.tsx
docs/realtime-logs.md
```

## Git 提交信息

```
feat: 添加实时日志流功能

- 实现 Celery Worker 日志通过 Redis Pub/Sub 实时推送
- 添加 WebSocket 端点 /api/v1/ws/logs 支持日志流
- 创建 LogViewer React 组件，支持实时显示和过滤
- 集成到任务中心 UI，添加「实时日志」导航
- 使用 loguru bind() 自动携带 task_id 上下文
- 支持按 task_id 过滤特定任务日志
- 添加完整文档和使用指南

技术栈：Redis Pub/Sub + FastAPI WebSocket + React
```
