---
name: crawl-request-entry
description: 爬虫需求的命令式入口别名。只要用户输入以 "/crawl-request" 开头并带有需求，就必须触发本技能。去掉前缀后将剩余文本作为任务需求，转交给 news-crawl-orchestrator 工作流。
---

# 爬虫请求入口

## 目的
提供一个清晰的命令式入口，用户可通过 `/crawl-request` 直接发起任务。

## 触发规则
当输入以 `/crawl-request` 开头时，必须触发本技能。

## 输入约定
- 原始格式：`/crawl-request <需求文本>`
- 去除 `/crawl-request` 前缀。
- 将剩余内容作为真实任务需求。

## 执行流程
1. 规范化需求文本。
2. 将需求交给 `news-crawl-orchestrator` 执行。
3. 输出格式保持与 orchestrator 一致。

## 示例
- `/crawl-request 为 example.com 新增一个来源爬虫并配置每小时调度`
- `/crawl-request 修复 craw_cnfin_thread 的列表提取并补充主备选择器`
- `/crawl-request 仅重跑一个来源，其他任务保持不变`
- `/crawl-request 为正文加入图片 Markdown 占位，使用公网链接且不上传 OSS/OBS`
