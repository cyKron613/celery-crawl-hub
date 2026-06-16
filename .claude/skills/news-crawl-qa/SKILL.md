---
name: news-crawl-qa
description: 对爬虫变更执行增量 QA。每次模块变更后，以及后续重跑或局部修复时，都应触发验证/审阅/审计/回归检查。重点关注爬虫输出、Celery 路由、调度触发与下游数据库字段形状的一致性。
---

# 新闻爬虫 QA

## 目标
在每次模块变更后执行增量验证，尽早发现集成边界缺陷。

## 检查维度
1. 任务模块路径与路由路径一致性
2. 调度配置与任务触发一致性
3. 输出字段形状与入库预期兼容性
4. 对同类任务模块的回归风险
5. 正文图片占位渲染有效性（Markdown 语法、图文顺序）
6. 正文图片链接策略一致性（公网原图链接，不引入 OSS/OBS 上传）

## 严重级别
- High：执行失败、队列错误、必填字段缺失
- Medium：日期/图片/正文提取不稳定
- Low：可维护性与可观测性不足

## 正文图片专项检查
- `detail_contents`/`detail_contents_cn` 中图片占位格式符合 `![图片{index}]({url})`
- 图片链接为可解析公网 URL，且已按详情页 URL 做相对路径归一化
- 不新增上传失败类异常（因为不走 OSS/OBS 上传链路）

## 输出模板
- Verdict: PASS | FAIL | BLOCKED
- Findings:
- Evidence:
- Suggested fixes:
- Retest plan:
