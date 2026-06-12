import type {
  ApiEnvelope,
  CrawlerTask,
  InsertedDataResult,
  TaskListResult,
  TaskFormData,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

function parseLines(value: string): string[] {
  return value
    .split('\n')
    .map((v) => v.trim())
    .filter(Boolean)
}

function parseXPath(value: string): string | string[] | null {
  const lines = parseLines(value)
  if (!lines.length) return null
  if (lines.length === 1) return lines[0]
  return lines
}

function stringifyXPath(value: unknown): string {
  if (!value) return ''
  if (Array.isArray(value)) return value.join('\n')
  return String(value)
}

export function taskToForm(task?: Partial<CrawlerTask>): TaskFormData {
  return {
    task_name: task?.task_name || '',
    description: task?.description || '',
    source_name: task?.source_name || '',
    prefix: task?.prefix || '',
    home_url_list: (task?.home_url_list || []).join('\n'),
    url_xpath: stringifyXPath(task?.url_xpath),
    title_xpath: stringifyXPath(task?.title_xpath),
    content_xpath: stringifyXPath(task?.content_xpath),
    home_date_xpath: stringifyXPath(task?.home_date_xpath),
    date_xpath: stringifyXPath(task?.date_xpath),
    image_xpath: stringifyXPath(task?.image_xpath),
    detail_image_xpath: stringifyXPath(task?.detail_image_xpath),
    url_limit: task?.url_limit || 10,
    list_retry_count: task?.list_retry_count || 1,
    list_retry_sleep_seconds: task?.list_retry_sleep_seconds || 3,
    detail_retry_count: task?.detail_retry_count || 0,
    detail_retry_sleep_seconds: task?.detail_retry_sleep_seconds || 2,
    min_content_length: task?.min_content_length || 0,
    max_content_length: task?.max_content_length || 0,
    dedupe_urls: !!task?.dedupe_urls,
    home_wait_xpath: stringifyXPath(task?.home_wait_xpath),
    detail_wait_xpath: stringifyXPath(task?.detail_wait_xpath),
    source_language: task?.source_language || 'auto',
    source_map: JSON.stringify(task?.source_map || {}, null, 2),
    content_joiner: task?.content_joiner || ' ',
    default_image_url: task?.default_image_url || '',
    date_patterns: (task?.date_patterns || []).join('\n'),
    schedule_type: task?.schedule_type || 'manual',
    cron_expression: task?.cron_expression || '',
    interval_seconds: task?.interval_seconds || 0,
    schedule_enabled: !!task?.schedule_enabled,
  }
}

export function formToPayload(form: TaskFormData) {
  const minContent = Math.max(0, Number(form.min_content_length || 0))
  const maxContent = Math.max(0, Number(form.max_content_length || 0))
  if (maxContent > 0 && maxContent < minContent) {
    throw new Error('max_content_length 不能小于 min_content_length')
  }

  let sourceMap: Record<string, string> = {}
  if (form.source_map.trim()) {
    const parsed = JSON.parse(form.source_map)
    if (typeof parsed !== 'object' || Array.isArray(parsed) || !parsed) {
      throw new Error('source_map 必须是 JSON 对象')
    }
    sourceMap = Object.fromEntries(Object.entries(parsed).map(([k, v]) => [String(k), String(v)]))
  }

  return {
    task_name: form.task_name.trim(),
    description: form.description.trim() || null,
    source_name: form.source_name.trim(),
    prefix: form.prefix.trim() || null,
    home_url_list: parseLines(form.home_url_list),
    url_xpath: parseXPath(form.url_xpath),
    title_xpath: parseXPath(form.title_xpath),
    content_xpath: parseXPath(form.content_xpath),
    home_date_xpath: parseXPath(form.home_date_xpath),
    date_xpath: parseXPath(form.date_xpath),
    image_xpath: parseXPath(form.image_xpath),
    detail_image_xpath: parseXPath(form.detail_image_xpath),
    url_limit: Number(form.url_limit || 10),
    list_retry_count: Number(form.list_retry_count || 0),
    list_retry_sleep_seconds: Number(form.list_retry_sleep_seconds || 0),
    detail_retry_count: Number(form.detail_retry_count || 0),
    detail_retry_sleep_seconds: Number(form.detail_retry_sleep_seconds || 0),
    min_content_length: minContent,
    max_content_length: maxContent,
    dedupe_urls: !!form.dedupe_urls,
    home_wait_xpath: parseXPath(form.home_wait_xpath),
    detail_wait_xpath: parseXPath(form.detail_wait_xpath),
    source_language: form.source_language.trim() || 'auto',
    source_map: sourceMap,
    content_joiner: form.content_joiner,
    default_image_url: form.default_image_url.trim() || null,
    date_patterns: parseLines(form.date_patterns),
    schedule_type: form.schedule_type,
    cron_expression: form.cron_expression.trim() || null,
    interval_seconds: form.interval_seconds > 0 ? Number(form.interval_seconds) : null,
    schedule_enabled: !!form.schedule_enabled,
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  })
  const data = (await res.json()) as ApiEnvelope<T>
  if (!res.ok) {
    throw new Error(data.message || `请求失败: ${res.status}`)
  }
  return data.data
}

export async function fetchTaskList(page: number, pageSize: number): Promise<TaskListResult> {
  const full = await fetch(`${API_BASE_URL}/v1/crawler/tasks?page=${page}&page_size=${pageSize}`)
  const data = (await full.json()) as ApiEnvelope<CrawlerTask[]>
  if (!full.ok) throw new Error(data.message || `请求失败: ${full.status}`)
  return {
    data: data.data || [],
    page: data.page || page,
    page_size: data.page_size || pageSize,
    total: data.total || 0,
    total_pages: data.total_pages || 1,
  }
}

export async function fetchTaskDetail(taskId: string): Promise<CrawlerTask> {
  return request<CrawlerTask>(`/v1/crawler/tasks/${taskId}`)
}

export async function createTask(payload: unknown): Promise<unknown> {
  return request('/v1/crawler/tasks', { method: 'POST', body: JSON.stringify(payload) })
}

export async function updateTask(taskId: string, payload: unknown): Promise<unknown> {
  return request(`/v1/crawler/tasks/${taskId}`, { method: 'PUT', body: JSON.stringify(payload) })
}

export async function runTask(taskId: string): Promise<unknown> {
  return request(`/v1/crawler/tasks/${taskId}/run`, { method: 'POST' })
}

export async function deleteTask(taskId: string): Promise<unknown> {
  return request(`/v1/crawler/tasks/${taskId}`, { method: 'DELETE' })
}

export async function fetchInsertedData(page: number, pageSize: number): Promise<InsertedDataResult> {
  const full = await fetch(`${API_BASE_URL}/v1/crawler/inserted-data?page=${page}&page_size=${pageSize}`)
  const data = (await full.json()) as ApiEnvelope<InsertedDataResult['data']>
  if (!full.ok) throw new Error(data.message || `请求失败: ${full.status}`)
  return {
    data: data.data || [],
    page: data.page || page,
    page_size: data.page_size || pageSize,
    total: data.total || 0,
    total_pages: data.total_pages || 1,
  }
}

export async function fetchLatestExecutionResult(taskId: string): Promise<unknown> {
  const executionListRes = await fetch(`${API_BASE_URL}/v1/crawler/tasks/${taskId}/executions?limit=1`)
  const executionList = (await executionListRes.json()) as ApiEnvelope<Array<{ celery_task_id?: string }>>
  if (!executionListRes.ok) {
    throw new Error(executionList.message || `请求失败: ${executionListRes.status}`)
  }
  const celeryTaskId = executionList.data?.[0]?.celery_task_id
  if (!celeryTaskId) {
    return { message: '当前任务暂无执行记录' }
  }
  return request(`/v1/crawler/executions/${celeryTaskId}/results`)
}

export async function testXPath(payload: {
  url: string
  xpath: string | string[]
  wait_xpath?: string | string[] | null
}): Promise<string[]> {
  const res = await fetch(`${API_BASE_URL}/v1/crawler/test-xpath`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const envelope = (await res.json()) as ApiEnvelope<{ extracted: string[] }>
  if (!res.ok || envelope.code !== 200) {
    throw new Error(envelope.message || `测试请求错误: ${res.status}`)
  }
  return envelope.data?.extracted || []
}
