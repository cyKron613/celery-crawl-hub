---
name: news-crawl-orchestrator
description: 使用代理团队编排本项目的爬虫工程流程。新增爬虫、重跑、再执行、更新、局部修复、结果改进、维护同步，以及优化 harness、同步 .claude 配置、切换分支后迁移旧分支的 harness 修改等请求都应触发本技能。若用户提到 "build harness"、"update harness"、"optimize harness"、"sync harness"、"switch branch"、"migrate harness changes"、"rerun part"、"improve previous result"、"fix only one source"，或使用 "/crawl-request ..." 命令式输入，必须触发本技能。涉及正文图片占位时，默认采用 Markdown 图片格式并使用公网原图链接，不引入 OSS/OBS 上传链路。
---

# 新闻爬虫编排器

## 快速入口
可通过命令式快捷方式 `/crawl-request <需求>` 发起任务。

## 执行模式
默认使用代理团队模式。

## 团队成员
- `harness-orchestrator` (leader, model: opus)
- `source-analyst` (analyst, model: opus)
- `crawler-engineer` (implementer, model: opus)
- `integration-qa` (qa, model: opus)

## Phase 0：审计
1. 检查 `.claude/agents/`、`.claude/skills/` 与 `CLAUDE.md`。
2. 缺失时走初始化路径；存在时走扩展/维护路径。
3. 检测声明团队与实际文件是否漂移。
4. 若请求涉及优化 harness 或切换分支，先确认需要同步的范围：`.claude/agents/`、`.claude/skills/`、`CLAUDE.md`、以及 `_workspace/` 中的中间工件。

## Phase 1：上下文检查（初次、后续、局部重跑）
1. 检查 `_workspace/` 是否存在。
2. 若存在且为局部修复，仅重跑受影响代理。
3. 若存在且包含新输入，将旧目录移动到 `_workspace_prev/` 后全量执行。
4. 若不存在，执行初次全流程。
5. 若用户说明后续会切换到新分支，先整理当前分支的 harness 变更清单；进入新分支后优先迁移 `.claude/` 与 `CLAUDE.md`，仅在需要保留历史证据时再迁移 `_workspace/`。
6. 对分支迁移类请求，输出明确的 handoff 清单：需要带走的文件、可丢弃的临时工件、以及进入新分支后的首轮校验项。

## Phase 2：拆分与分配
1. 将任务拆分为来源分析、代码实现、增量 QA。
2. 使用 TaskCreate 跟踪依赖。
3. 使用 SendMessage 实时协同。
4. 若需求包含正文图片处理，显式拆分“正文顺序保留 + 图片占位格式 + 链接策略”三个子任务，并约束为最小改动。

## Phase 3：执行
1. `source-analyst` 输出字段映射与主备选择器。
2. `crawler-engineer` 落地代码和 Celery 配置，**必须同时生成 SQL 插入语句和 Python 模板代码**：
   - SQL 文件：`sql/{source_name}_news.sql` — 插入 `crawler_tasks` 表
   - Python 模板：`sql/{source_name}_template.py` — 继承 `XPathCrawlerTaskBase`
   - 两份产出物的 XPath、调度参数、custom_methods 必须完全一致
3. `integration-qa` 执行边界面检查，**验证 SQL 和 Python 模板字段一致性**。
4. 正文图片类需求默认执行策略：
	- 占位格式：`![图片{index}]({url})`
	- 链接来源：详情页归一化后的公网链接
	- 数据链路：不新增 OSS/OBS 上传步骤，避免引入额外依赖

## Phase 4：整合
1. 汇总变更与验证结论。
2. 每个失败单元重试 1 次；仍失败则标注缺失与影响。
3. 返回可执行的后续动作。
4. 若本次目标包含 harness 维护，单独给出 branch handoff 小结，说明哪些改动必须 cherry-pick 或直接复制到新分支。

## 数据传递协议
- 协同：TaskCreate 与 TaskUpdate
- 实时沟通：SendMessage
- 工件：`_workspace/{phase}_{agent}_{artifact}.md`

## 错误处理
- 单点失败重试 1 次。
- 重试失败后保留证据并继续其他任务。
- 对冲突信息保留来源归因，不做静默覆盖。
- 分支迁移前若发现未整理的 harness 改动，先输出待迁移清单，再继续执行其他维护步骤。

## 测试场景
### 正常流程
输入："新增一个二级来源爬虫并配置每小时调度"
期望：任务文件更新、路由/调度更新、QA 报告。

### 异常流程
输入："修复一个爬虫，但列表因反爬返回空"
期望：输出备选选择器、重试轨迹、阻塞说明、部分完成报告。

### 维护流程
输入："补充优化当前项目的 harness，后续我会切换到新的分支补充旧的分支修改带到新的分支"
期望：审计现有 `.claude/` 与 `CLAUDE.md`，补充后续维护与分支迁移规则，输出可直接带到新分支的 handoff 清单。

### 正文图片流程
输入："补充正文加入图片占位，直接用公网链接展示"
期望：在基类/任务中保留图文顺序，正文直接插入 Markdown 图片语法，QA 验证渲染与字段兼容。

## 触发边界
- 应触发：新增来源、任务修复、局部重跑、结果更新、维护同步。
- 不触发：纯概念问答。
