import { useEffect, useState } from 'react'
import {
  createTask,
  deleteTask,
  fetchInsertedData,
  fetchLatestExecutionResult,
  fetchTaskDetail,
  fetchTaskList,
  formToPayload,
  runTask,
  taskToForm,
  updateTask,
  testXPath,
} from './api'
import type { CrawlerTask, InsertedDataItem, TaskFormData } from './types'

type Panel = 'tasks' | 'editor' | 'inserted'

const emptyForm: TaskFormData = taskToForm()
const createTemplateForm = (): TaskFormData => ({
  ...taskToForm(),
  task_name: '模板任务-示例站点',
  description: '一键模板，请按目标站点调整 XPath 与 URL。',
  source_name: 'template-source',
  source_language: 'en',
  home_url_list: 'https://example.com/news',
  url_xpath: '//article//a/@href',
  title_xpath: '//h1/text()',
  content_xpath: '//article//p/text()',
  date_xpath: '//time/@datetime',
  url_limit: 20,
  list_retry_count: 2,
  list_retry_sleep_seconds: 3,
  detail_retry_count: 1,
  detail_retry_sleep_seconds: 2,
  dedupe_urls: true,
  content_joiner: '\n',
  date_patterns: '%Y-%m-%d\n%Y-%m-%d %H:%M:%S\n%b %d, %Y',
  schedule_type: 'manual',
  schedule_enabled: false,
})

type OnTaskFieldChange = <K extends keyof TaskFormData>(key: K, value: TaskFormData[K]) => void

const DEFAULT_PYTHON_TEMPLATE = `class SCOCrawlerTask(XPathCrawlerTaskBase):
    source_name = "sco"
    prefix = "https://eng.sectsco.org"
    home_url_list = [
        'https://eng.sectsco.org/search/'
    ]
    url_xpath = '//article[@class="list-item"]/a/@href'
    date_xpath = "//time[@class='article-header__date']//text()"
    title_xpath = '//h1[@class="article-header__title"]//text()'
    content_xpath = "//div[@class='article-body__block article-body__block_text']//text()"
    image_xpath = "//fugure[@class='list-item__image']//img/@src"

    detail_wait_xpath = '//h1[@class="article-header__title"]'
    detail_retry_count = 1
    detail_retry_sleep_seconds = 2
`

// ── Python 模板解析 ──────────────────────────────────────────────

/** XPathCrawlerTaskBase 中所有可映射到 TaskFormData 的属性名集合 */
const MAPPABLE_KEYS = new Set<string>([
  'source_name', 'prefix', 'home_url_list',
  'url_xpath', 'title_xpath', 'content_xpath',
  'home_date_xpath', 'date_xpath', 'image_xpath', 'detail_image_xpath',
  'url_limit', 'list_retry_count', 'list_retry_sleep_seconds',
  'detail_retry_count', 'detail_retry_sleep_seconds',
  'home_request_delay_seconds', 'home_request_delay_jitter_seconds',
  'detail_request_delay_seconds', 'detail_request_delay_jitter_seconds',
  'dedupe_urls', 'home_wait_xpath', 'detail_wait_xpath',
  'fetch_timeout', 'min_content_length', 'max_content_length',
  'login_enabled', 'login_username', 'login_password',
  'playwright_login_url', 'playwright_login_entry_xpath',
  'playwright_login_username_xpath', 'playwright_login_password_xpath',
  'playwright_login_submit_xpath', 'playwright_login_success_xpath',
  'playwright_login_timeout', 'playwright_headless',
  'enable_content_image_placeholder',
  'content_root_xpath', 'content_image_xpath',
  'content_image_placeholder_template', 'append_content_image_mapping',
  'source_language', 'source_map', 'category',
  'content_joiner', 'default_image_url', 'date_patterns',
])

/** 从 Python 源码中提取指定 class 体的文本 */
function extractClassBody(source: string, baseClassName: string): string | null {
  // 匹配 class Xxx(XPathCrawlerTaskBase): 或 class Xxx(XPathCrawlerTaskBase, ...):
  const classPattern = new RegExp(
    `class\\s+\\w+\\s*\\([^)]*${baseClassName}[^)]*\\)\\s*:`,
    'm',
  )
  const match = classPattern.exec(source)
  if (!match) return null

  const bodyStart = match.index + match[0].length
  // 类体 = 从 class 行之后到下一个非缩进行（或文件结尾）
  const lines = source.slice(bodyStart).split('\n')
  const bodyLines: string[] = []
  for (const line of lines) {
    // 空行或缩进行属于类体
    if (line.trim() === '' || /^\s+/.test(line)) {
      bodyLines.push(line)
    } else {
      break
    }
  }
  return bodyLines.join('\n')
}

/** 解析 Python 字面量值 → JS 值 */
function parsePythonValue(raw: string): unknown {
  const trimmed = raw.trim()

  // 布尔
  if (trimmed === 'True') return true
  if (trimmed === 'False') return false
  if (trimmed === 'None') return null

  // 数字
  if (/^-?\d+$/.test(trimmed)) return parseInt(trimmed, 10)
  if (/^-?\d+\.\d+$/.test(trimmed)) return parseFloat(trimmed)

  // 字符串（单引号或双引号，支持三引号）
  const strMatch = trimmed.match(/^(?:"""([\s\S]*?)"""|'''([\s\S]*?)'''|"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')$/)
  if (strMatch) {
    return strMatch[1] ?? strMatch[2] ?? strMatch[3] ?? strMatch[4] ?? ''
  }

  // 列表 [...]
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    const inner = trimmed.slice(1, -1).trim()
    if (!inner) return []
    // 简单拆分：按逗号分割，逐个解析
    const items: unknown[] = []
    let depth = 0
    let current = ''
    for (let i = 0; i < inner.length; i++) {
      const ch = inner[i]
      if (ch === '[' || ch === '(' || ch === '{') depth++
      else if (ch === ']' || ch === ')' || ch === '}') depth--
      if (ch === ',' && depth === 0) {
        items.push(parsePythonValue(current))
        current = ''
      } else {
        current += ch
      }
    }
    if (current.trim()) items.push(parsePythonValue(current))
    return items
  }

  // 字典 {...}
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    const inner = trimmed.slice(1, -1).trim()
    if (!inner) return {}
    const result: Record<string, unknown> = {}
    // 简单 key: value 拆分
    let depth = 0
    let current = ''
    const pairs: string[] = []
    for (let i = 0; i < inner.length; i++) {
      const ch = inner[i]
      if (ch === '[' || ch === '(' || ch === '{') depth++
      else if (ch === ']' || ch === ')' || ch === '}') depth--
      if (ch === ',' && depth === 0) {
        pairs.push(current)
        current = ''
      } else {
        current += ch
      }
    }
    if (current.trim()) pairs.push(current)
    for (const pair of pairs) {
      const colonIdx = pair.indexOf(':')
      if (colonIdx > 0) {
        const key = parsePythonValue(pair.slice(0, colonIdx)) as string
        const val = parsePythonValue(pair.slice(colonIdx + 1))
        result[String(key)] = val
      }
    }
    return result
  }

  // 无法解析，返回原始字符串
  return trimmed
}

/** 从 Python 类体中提取所有 class-level 属性赋值 */
function parseClassAttributes(classBody: string): Record<string, unknown> {
  const attrs: Record<string, unknown> = {}
  // 匹配: 属性名 = 值（值可能跨多行，如列表）
  // 策略：逐行扫描，遇到 `name = ...` 开始收集，直到下一个 `name = ...` 或结束
  const lines = classBody.split('\n')
  let currentKey = ''
  let currentValue = ''

  function flush() {
    if (currentKey && MAPPABLE_KEYS.has(currentKey)) {
      attrs[currentKey] = parsePythonValue(currentValue)
    }
    currentKey = ''
    currentValue = ''
  }

  for (const line of lines) {
    const stripped = line.trim()
    // 跳过注释和空行
    if (!stripped || stripped.startsWith('#')) continue
    // 跳过 def / @decorator / if __name__ 等
    if (stripped.startsWith('def ') || stripped.startsWith('@') || stripped.startsWith('if ')) {
      flush()
      continue
    }

    // 尝试匹配 `key = value` 或 `key: type = value`
    const assignMatch = stripped.match(/^(\w+)\s*(?::\s*\S+\s*)?=\s*(.*)$/)
    if (assignMatch && !line.startsWith(' ') === false && /^\s{4}\w/.test(line)) {
      // 这是类属性赋值（4空格缩进）
      flush()
      currentKey = assignMatch[1]
      currentValue = assignMatch[2]
    } else if (currentKey) {
      // 多行值的续行
      currentValue += ' ' + stripped
    }
  }
  flush()
  return attrs
}

/** 将解析出的 Python 属性映射为 Partial<CrawlerTask> 供 taskToForm 使用 */
function pythonAttrsToTaskPartial(attrs: Record<string, unknown>): Partial<CrawlerTask> {
  const partial: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined) continue
    partial[key] = value
  }
  return partial as Partial<CrawlerTask>
}

/** 解析 Python 模板文件，返回可映射的属性字典 */
function parsePythonTemplate(source: string): { attrs: Record<string, unknown>; className: string } {
  // 校验：必须 import XPathCrawlerTaskBase
  if (!source.includes('XPathCrawlerTaskBase')) {
    throw new Error('模板必须导入 XPathCrawlerTaskBase（from src.utils.xpath_crawler_base import XPathCrawlerTaskBase）')
  }

  // 校验：必须有继承 XPathCrawlerTaskBase 的类
  const classMatch = source.match(/class\s+(\w+)\s*\([^)]*XPathCrawlerTaskBase[^)]*\)\s*:/)
  if (!classMatch) {
    throw new Error('模板必须定义一个继承 XPathCrawlerTaskBase 的类')
  }
  const className = classMatch[1]

  const classBody = extractClassBody(source, 'XPathCrawlerTaskBase')
  if (!classBody) {
    throw new Error(`无法提取类 ${className} 的定义体`)
  }

  const attrs = parseClassAttributes(classBody)

  // 校验：至少要有 source_name
  if (!attrs.source_name) {
    throw new Error('模板类必须定义 source_name 属性')
  }

  return { attrs, className }
}

function App() {
  const [panel, setPanel] = useState<Panel>('tasks')
  const [tasks, setTasks] = useState<CrawlerTask[]>([])
  const [loadingTasks, setLoadingTasks] = useState(false)
  const [tasksPage, setTasksPage] = useState(1)
  const [tasksPageSize, setTasksPageSize] = useState(20)
  const [tasksTotalPages, setTasksTotalPages] = useState(1)
  const [taskStatus, setTaskStatus] = useState('等待加载任务')

  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [editingTaskId, setEditingTaskId] = useState('')
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [executionResult, setExecutionResult] = useState('{}')

  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create')
  const [form, setForm] = useState<TaskFormData>(emptyForm)
  const [editorStatus, setEditorStatus] = useState('')
  const [editorOutput, setEditorOutput] = useState('{}')

  const [inserted, setInserted] = useState<InsertedDataItem[]>([])
  const [insertedPage, setInsertedPage] = useState(1)
  const [insertedPageSize, setInsertedPageSize] = useState(20)
  const [insertedTotalPages, setInsertedTotalPages] = useState(1)
  const [insertedStatus, setInsertedStatus] = useState('等待加载入库数据')

  const [templateModalOpen, setTemplateModalOpen] = useState(false)
  const [templateSource, setTemplateSource] = useState(DEFAULT_PYTHON_TEMPLATE)
  const [templateError, setTemplateError] = useState('')

  async function loadTasks(targetPage = tasksPage, pageSize = tasksPageSize) {
    setLoadingTasks(true)
    try {
      const result = await fetchTaskList(targetPage, pageSize)
      setTasks(result.data)
      setTasksPage(result.page)
      setTasksTotalPages(result.total_pages || 1)
      setTaskStatus(`已加载 ${result.data.length} 条任务，共 ${result.total} 条`)
      if (!selectedTaskId && result.data.length) {
        setSelectedTaskId(result.data[0].id)
      }
    } catch (error) {
      setTaskStatus(`任务加载失败: ${(error as Error).message}`)
    } finally {
      setLoadingTasks(false)
    }
  }

  async function loadExecution(taskId: string) {
    if (!taskId) return
    try {
      const result = await fetchLatestExecutionResult(taskId)
      setExecutionResult(JSON.stringify(result, null, 2))
    } catch (error) {
      setExecutionResult(JSON.stringify({ error: (error as Error).message }, null, 2))
    }
  }

  async function loadTaskIntoEditor(taskId: string, mode: 'panel' | 'modal' = 'panel') {
    if (!taskId) return
    try {
      const detail = await fetchTaskDetail(taskId)
      setSelectedTaskId(taskId)
      setEditingTaskId(taskId)
      setEditorMode('edit')
      setForm(taskToForm(detail))
      setEditorOutput('{}')
      setEditorStatus(`已载入任务: ${detail.task_name}`)
      if (mode === 'panel') {
        setPanel('editor')
      } else {
        setEditModalOpen(true)
      }
    } catch (error) {
      setEditorStatus(`加载失败: ${(error as Error).message}`)
    }
  }

  async function submitEditor(): Promise<boolean> {
    try {
      const payload = formToPayload(form)
      let result: unknown
      if (editorMode === 'create') {
        result = await createTask(payload)
        setEditorStatus('创建成功')
      } else {
        if (!editingTaskId) {
          throw new Error('请先选择一个任务再保存')
        }
        result = await updateTask(editingTaskId, payload)
        setEditorStatus('保存成功')
      }
      setEditorOutput(JSON.stringify(result, null, 2))
      await loadTasks(1, tasksPageSize)
      return true
    } catch (error) {
      setEditorStatus(`提交失败: ${(error as Error).message}`)
      return false
    }
  }

  async function removeTaskById(taskId: string) {
    if (!taskId) return
    const ok = window.confirm('确认删除该任务吗？该操作不可撤销。')
    if (!ok) return
    try {
      await deleteTask(taskId)
      setTaskStatus('删除成功')
      if (selectedTaskId === taskId) {
        setSelectedTaskId('')
      }
      if (editingTaskId === taskId) {
        setEditingTaskId('')
        setEditModalOpen(false)
      }
      await loadTasks(1, tasksPageSize)
      setExecutionResult('{}')
    } catch (error) {
      setTaskStatus(`删除失败: ${(error as Error).message}`)
    }
  }

  function applyCreateTemplate() {
    setEditorMode('create')
    setEditingTaskId('')
    setForm(createTemplateForm())
    setEditorStatus('已填充模板，请按目标站点调整后创建')
  }

  function openTemplateModal() {
    setTemplateSource(DEFAULT_PYTHON_TEMPLATE)
    setTemplateError('')
    setTemplateModalOpen(true)
  }

  function applyTemplateToForm() {
    try {
      const { attrs, className } = parsePythonTemplate(templateSource)
      const partial = pythonAttrsToTaskPartial(attrs)
      const formData = taskToForm(partial)
      setForm(formData)
      setEditorMode('create')
      setEditingTaskId('')
      setTemplateModalOpen(false)
      setEditorStatus(`已从模板 ${className} 生成配置，请检查后创建任务`)
      setPanel('editor')
    } catch (err) {
      setTemplateError(`模板解析失败: ${(err as Error).message}`)
    }
  }

  async function executeNow() {
    if (!selectedTaskId) return
    try {
      const result = await runTask(selectedTaskId)
      setTaskStatus('任务已提交执行')
      setExecutionResult(JSON.stringify(result, null, 2))
      await loadTasks(tasksPage, tasksPageSize)
      await loadExecution(selectedTaskId)
    } catch (error) {
      setTaskStatus(`执行失败: ${(error as Error).message}`)
    }
  }

  async function removeTask() {
    if (!selectedTaskId) return
    await removeTaskById(selectedTaskId)
  }

  async function loadInserted(page = insertedPage, pageSize = insertedPageSize) {
    try {
      const result = await fetchInsertedData(page, pageSize)
      setInserted(result.data)
      setInsertedPage(result.page)
      setInsertedTotalPages(result.total_pages || 1)
      setInsertedStatus(`已加载 ${result.data.length} 条数据，共 ${result.total} 条`)
    } catch (error) {
      setInsertedStatus(`加载失败: ${(error as Error).message}`)
    }
  }

  function onField<K extends keyof TaskFormData>(key: K, value: TaskFormData[K]) {
    setForm((prev: TaskFormData) => ({ ...prev, [key]: value }))
  }

  useEffect(() => {
    void loadTasks(1, tasksPageSize)
  }, [tasksPageSize])

  useEffect(() => {
    if (selectedTaskId) {
      void loadExecution(selectedTaskId)
    }
  }, [selectedTaskId])

  useEffect(() => {
    if (panel === 'inserted') {
      void loadInserted(1, insertedPageSize)
    }
  }, [panel, insertedPageSize])

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Crawler Platform</h1>
        <p>现代化任务平台，覆盖 Gradio 核心能力</p>
        <button className={panel === 'tasks' ? 'nav active' : 'nav'} onClick={() => setPanel('tasks')}>
          任务中心
        </button>
        <button
          className={panel === 'editor' ? 'nav active' : 'nav'}
          onClick={() => {
            if (selectedTaskId) {
              void loadTaskIntoEditor(selectedTaskId)
            } else {
              setEditorMode('create')
              setEditingTaskId('')
              setPanel('editor')
            }
          }}
        >
          创建/编辑任务
        </button>
        <button className={panel === 'inserted' ? 'nav active' : 'nav'} onClick={() => setPanel('inserted')}>
          入库数据
        </button>
        <button
          className="nav secondary"
          onClick={() => {
            setEditorMode('create')
            setEditingTaskId('')
            setForm(emptyForm)
            setEditorStatus('已切换到创建模式')
            setPanel('editor')
          }}
        >
          新建任务
        </button>
      </aside>

      <main className="main">
        {panel === 'tasks' && (
          <section className="panel">
            <header className="panel-head">
              <h2>任务中心</h2>
              <div className="actions">
                <button onClick={() => void loadTasks(tasksPage, tasksPageSize)} disabled={loadingTasks}>
                  {loadingTasks ? '刷新中...' : '刷新'}
                </button>
                <button className="ok" onClick={() => void executeNow()} disabled={!selectedTaskId}>
                  立即执行
                </button>
                <button className="danger" onClick={() => void removeTask()} disabled={!selectedTaskId}>
                  删除任务
                </button>
              </div>
            </header>
            <p className="status">{taskStatus}</p>
            <div className="filters">
              <label>
                每页
                <select value={tasksPageSize} onChange={(e) => setTasksPageSize(Number(e.target.value))}>
                  {[10, 20, 50, 100].map((v) => (
                    <option value={v} key={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                任务
                <select value={selectedTaskId} onChange={(e) => setSelectedTaskId(e.target.value)}>
                  <option value="">请选择</option>
                  {tasks.map((t) => (
                    <option value={t.id} key={t.id}>
                      {t.task_name} | {t.source_name}
                    </option>
                  ))}
                </select>
              </label>
              <button onClick={() => selectedTaskId && void loadTaskIntoEditor(selectedTaskId)} disabled={!selectedTaskId}>
                载入到编辑器
              </button>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>任务</th>
                    <th>来源</th>
                    <th>调度</th>
                    <th>状态</th>
                    <th>最近运行</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t) => (
                    <tr key={t.id} className={t.id === selectedTaskId ? 'selected' : ''} onClick={() => setSelectedTaskId(t.id)}>
                      <td>{t.task_name}</td>
                      <td>{t.source_name}</td>
                      <td>{t.schedule_type}{t.schedule_enabled ? ' (启用)' : ''}</td>
                      <td>{t.last_status || 'idle'}</td>
                      <td>{t.last_run_at || '-'}</td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="mini"
                            onClick={(e) => {
                              e.stopPropagation()
                              void loadTaskIntoEditor(t.id, 'modal')
                            }}
                          >
                            编辑
                          </button>
                          <button
                            className="mini danger"
                            onClick={(e) => {
                              e.stopPropagation()
                              void removeTaskById(t.id)
                            }}
                          >
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!tasks.length && (
                    <tr>
                      <td colSpan={6}>暂无任务</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button onClick={() => void loadTasks(Math.max(1, tasksPage - 1), tasksPageSize)} disabled={tasksPage <= 1}>
                上一页
              </button>
              <span>
                第 {tasksPage} / {tasksTotalPages} 页
              </span>
              <button onClick={() => void loadTasks(tasksPage + 1, tasksPageSize)} disabled={tasksPage >= tasksTotalPages}>
                下一页
              </button>
            </div>
            <details className="code-block">
              <summary>最近执行结果</summary>
              <pre>{executionResult}</pre>
            </details>

            {editModalOpen && (
              <div className="modal-backdrop" onClick={() => setEditModalOpen(false)}>
                <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
                  <header className="panel-head">
                    <h2>弹框编辑任务</h2>
                    <div className="actions">
                      <button onClick={() => setEditModalOpen(false)}>关闭</button>
                      <button
                        className="ok"
                        onClick={async () => {
                          const ok = await submitEditor()
                          if (ok) {
                            setEditModalOpen(false)
                          }
                        }}
                      >
                        保存修改
                      </button>
                    </div>
                  </header>
                  <p className="status">{editorStatus || '修改字段后点击保存'}</p>
                  <TaskFormSections form={form} onField={onField} />
                </div>
              </div>
            )}
          </section>
        )}

        {panel === 'editor' && (
          <section className="panel">
            <header className="panel-head">
              <h2>{editorMode === 'create' ? '创建任务' : '编辑任务'}</h2>
              <div className="actions">
                {editorMode === 'create' && (
                  <>
                    <button onClick={applyCreateTemplate}>一键填充模板</button>
                    <button onClick={openTemplateModal}>
                      模板编辑器
                    </button>
                  </>
                )}
                <button onClick={() => {
                  setEditorMode('create')
                  setEditingTaskId('')
                  setForm(emptyForm)
                  setEditorStatus('已重置为空白任务')
                }}>
                  重置
                </button>
                <button className="ok" onClick={() => void submitEditor()}>
                  {editorMode === 'create' ? '创建任务' : '保存修改'}
                </button>
              </div>
            </header>
            {templateError && <p className="status error">{templateError}</p>}
            <p className="status">{editorStatus || '按分组完成配置后提交'}</p>
            <TaskFormSections form={form} onField={onField} />

            <details className="code-block">
              <summary>提交结果</summary>
              <pre>{editorOutput}</pre>
            </details>
          </section>
        )}

        {panel === 'inserted' && (
          <section className="panel">
            <header className="panel-head">
              <h2>正式入库数据</h2>
              <div className="actions">
                <label>
                  每页
                  <select value={insertedPageSize} onChange={(e) => setInsertedPageSize(Number(e.target.value))}>
                    {[20, 50, 100, 200].map((v) => (
                      <option value={v} key={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </label>
                <button onClick={() => void loadInserted(insertedPage, insertedPageSize)}>刷新</button>
              </div>
            </header>
            <p className="status">{insertedStatus}</p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>article_id</th>
                    <th>标题</th>
                    <th>来源</th>
                    <th>日期</th>
                    <th>分类</th>
                    <th>链接</th>
                  </tr>
                </thead>
                <tbody>
                  {inserted.map((row) => (
                    <tr key={row.article_id}>
                      <td>{row.article_id}</td>
                      <td>{row.detail_title_cn || row.detail_title || '-'}</td>
                      <td>{row.news_source_name_cn || '-'}</td>
                      <td>{row.detail_date || '-'}</td>
                      <td>{row.class_level_1 || '-'}</td>
                      <td className="url-cell">{row.detail_url || '-'}</td>
                    </tr>
                  ))}
                  {!inserted.length && (
                    <tr>
                      <td colSpan={6}>暂无数据</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button onClick={() => void loadInserted(Math.max(1, insertedPage - 1), insertedPageSize)} disabled={insertedPage <= 1}>
                上一页
              </button>
              <span>
                第 {insertedPage} / {insertedTotalPages} 页
              </span>
              <button onClick={() => void loadInserted(insertedPage + 1, insertedPageSize)} disabled={insertedPage >= insertedTotalPages}>
                下一页
              </button>
            </div>
          </section>
        )}
      </main>

      {templateModalOpen && (
        <div className="modal-backdrop" onClick={() => setTemplateModalOpen(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <header className="panel-head">
              <h2>Python 模板编辑器</h2>
              <div className="actions">
                <button onClick={() => setTemplateModalOpen(false)}>取消</button>
                <button className="ok" onClick={applyTemplateToForm}>
                  生成配置
                </button>
              </div>
            </header>
            {templateError && <p className="status error">{templateError}</p>}
            <p className="status">
              编辑继承 <code>XPathCrawlerTaskBase</code> 的类，点击「生成配置」将属性映射到表单（不会直接创建任务）
            </p>
            <textarea
              className="template-python-editor"
              value={templateSource}
              onChange={(e) => {
                setTemplateSource(e.target.value)
                setTemplateError('')
              }}
              rows={28}
              spellCheck={false}
              placeholder="在此编辑 Python 爬虫类定义..."
            />
          </div>
        </div>
      )}
    </div>
  )
}

function Field(props: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <input value={props.value} onChange={(e) => props.onChange(e.target.value)} />
    </label>
  )
}

function TextArea(props: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <textarea rows={4} value={props.value} onChange={(e) => props.onChange(e.target.value)} />
    </label>
  )
}

function NumberField(props: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <input type="number" value={props.value} onChange={(e) => props.onChange(Number(e.target.value || 0))} />
    </label>
  )
}

function SelectField(props: {
  label: string
  value: string
  options: Array<{ value: string; label: string }>
  onChange: (value: string) => void
}) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <select value={props.value} onChange={(e) => props.onChange(e.target.value)}>
        {props.options.map((opt) => (
          <option value={opt.value} key={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function CheckField(props: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="field checkbox">
      <span>{props.label}</span>
      <input type="checkbox" checked={props.checked} onChange={(e) => props.onChange(e.target.checked)} />
    </label>
  )
}

function XPathFieldWithTest(props: {
  label: string
  value: string
  onChange: (value: string) => void
  waitXPath?: string | null
}) {
  const [testUrl, setTestUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [extracted, setExtracted] = useState<string[]>([])
  const [errorMsg, setErrorMsg] = useState('')
  const [checked, setChecked] = useState(false)

  async function handleTest() {
    if (!testUrl.trim()) {
      setErrorMsg('请输入测试目标网页 URL')
      setExtracted([])
      setChecked(false)
      return
    }
    if (!props.value.trim()) {
      setErrorMsg('请输入 XPath 提取规则')
      setExtracted([])
      setChecked(false)
      return
    }
    setLoading(true)
    setErrorMsg('')
    setExtracted([])
    setChecked(false)
    try {
      const results = await testXPath({
        url: testUrl.trim(),
        xpath: props.value.split('\n').filter(Boolean),
        wait_xpath: props.waitXPath ? props.waitXPath.split('\n').filter(Boolean) : null,
      })
      setExtracted(results)
      setChecked(true)
    } catch (err) {
      setErrorMsg((err as Error).message)
      setChecked(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="xpath-testable-field">
      <label className="field">
        <span>{props.label}</span>
        <textarea
          rows={3}
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
        />
      </label>
      <div className="xpath-test-controls">
        <input
          type="text"
          placeholder="🎯 输入测试网页 URL..."
          value={testUrl}
          onChange={(e) => setTestUrl(e.target.value)}
          className="xpath-test-url-input"
        />
        <button
          type="button"
          onClick={() => void handleTest()}
          disabled={loading}
          className="xpath-test-btn"
        >
          {loading ? '正在提取...' : '验证 XPath'}
        </button>
        {checked && <span className="indicator-success">✔ 提取成功 ({extracted.length}条)</span>}
        {errorMsg && <span className="indicator-failed">❌ 提取失败</span>}
      </div>
      {errorMsg && (
        <div className="xpath-test-error">
          <strong>错误详情:</strong> {errorMsg}
        </div>
      )}
      {extracted.length > 0 && (
        <div className="xpath-test-results">
          <strong>第一页提取预览 (最多展示5条):</strong>
          <ul>
            {extracted.slice(0, 5).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
            {extracted.length > 5 && <li>... 还有 {extracted.length - 5} 条提取已省略</li>}
          </ul>
        </div>
      )}
    </div>
  )
}

function TaskFormSections(props: { form: TaskFormData; onField: OnTaskFieldChange }) {
  const { form, onField } = props

  return (
    <>
      <details open>
        <summary>1. 基础信息</summary>
        <div className="grid three">
          <Field label="任务标题" value={form.task_name} onChange={(v) => onField('task_name', v)} />
          <Field label="来源标识" value={form.source_name} onChange={(v) => onField('source_name', v)} />
          <Field label="来源语言" value={form.source_language} onChange={(v) => onField('source_language', v)} />
        </div>
        <Field label="任务描述" value={form.description} onChange={(v) => onField('description', v)} />
        <Field label="URL 前缀" value={form.prefix} onChange={(v) => onField('prefix', v)} />
        <TextArea label="首页 URL 列表" value={form.home_url_list} onChange={(v) => onField('home_url_list', v)} />
      </details>

      <details open>
        <summary>2. 解析规则与一键测试</summary>
        <div className="xpath-testable-grid">
          <XPathFieldWithTest label="列表链接 XPath" value={form.url_xpath} onChange={(v) => onField('url_xpath', v)} waitXPath={form.home_wait_xpath} />
          <XPathFieldWithTest label="标题 XPath" value={form.title_xpath} onChange={(v) => onField('title_xpath', v)} waitXPath={form.detail_wait_xpath} />
          <XPathFieldWithTest label="正文 XPath" value={form.content_xpath} onChange={(v) => onField('content_xpath', v)} waitXPath={form.detail_wait_xpath} />
          <XPathFieldWithTest label="列表日期 XPath" value={form.home_date_xpath} onChange={(v) => onField('home_date_xpath', v)} waitXPath={form.home_wait_xpath} />
          <XPathFieldWithTest label="详情日期 XPath" value={form.date_xpath} onChange={(v) => onField('date_xpath', v)} waitXPath={form.detail_wait_xpath} />
          <XPathFieldWithTest label="详情图片 XPath" value={form.detail_image_xpath} onChange={(v) => onField('detail_image_xpath', v)} waitXPath={form.detail_wait_xpath} />
          <TextArea label="首页等待 XPath" value={form.home_wait_xpath} onChange={(v) => onField('home_wait_xpath', v)} />
          <TextArea label="详情等待 XPath" value={form.detail_wait_xpath} onChange={(v) => onField('detail_wait_xpath', v)} />
        </div>
      </details>

      <details>
        <summary>3. 抓取策略与调度</summary>
        <div className="grid five">
          <NumberField label="抓取上限" value={form.url_limit} onChange={(v) => onField('url_limit', v)} />
          <NumberField label="列表重试" value={form.list_retry_count} onChange={(v) => onField('list_retry_count', v)} />
          <NumberField label="列表重试间隔" value={form.list_retry_sleep_seconds} onChange={(v) => onField('list_retry_sleep_seconds', v)} />
          <NumberField label="详情重试" value={form.detail_retry_count} onChange={(v) => onField('detail_retry_count', v)} />
          <NumberField label="详情重试间隔" value={form.detail_retry_sleep_seconds} onChange={(v) => onField('detail_retry_sleep_seconds', v)} />
        </div>
        <div className="grid four">
          <NumberField label="最小正文长度" value={form.min_content_length} onChange={(v) => onField('min_content_length', v)} />
          <NumberField label="最大正文长度" value={form.max_content_length} onChange={(v) => onField('max_content_length', v)} />
          <Field label="Cron 表达式" value={form.cron_expression} onChange={(v) => onField('cron_expression', v)} />
          <NumberField label="间隔秒" value={form.interval_seconds} onChange={(v) => onField('interval_seconds', v)} />
        </div>
        <div className="grid four">
          <SelectField
            label="调度类型"
            value={form.schedule_type}
            options={[
              { value: 'manual', label: 'manual' },
              { value: 'interval', label: 'interval' },
              { value: 'cron', label: 'cron' },
            ]}
            onChange={(v) => onField('schedule_type', v as TaskFormData['schedule_type'])}
          />
          <CheckField label="URL 去重" checked={form.dedupe_urls} onChange={(v) => onField('dedupe_urls', v)} />
          <CheckField label="启用调度" checked={form.schedule_enabled} onChange={(v) => onField('schedule_enabled', v)} />
        </div>
      </details>

      <details>
        <summary>4. 来源映射与日期格式</summary>
        <div className="grid two">
          <TextArea label="来源映射 JSON" value={form.source_map} onChange={(v) => onField('source_map', v)} />
          <TextArea label="日期格式列表" value={form.date_patterns} onChange={(v) => onField('date_patterns', v)} />
        </div>
      </details>
    </>
  )
}

export default App
