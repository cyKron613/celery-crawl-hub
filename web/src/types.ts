export type XPathInput = string | string[] | null

export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  page?: number
  page_size?: number
  total?: number
  total_pages?: number
}

export interface CrawlerTask {
  id: string
  task_name: string
  description?: string | null
  source_name: string
  prefix?: string | null
  home_url_list: string[]
  url_xpath: XPathInput
  title_xpath: XPathInput
  content_xpath: XPathInput
  home_date_xpath?: XPathInput
  date_xpath?: XPathInput
  image_xpath?: XPathInput
  detail_image_xpath?: XPathInput
  url_limit: number
  list_retry_count: number
  list_retry_sleep_seconds: number
  detail_retry_count: number
  detail_retry_sleep_seconds: number
  min_content_length: number
  max_content_length: number
  dedupe_urls: boolean
  home_wait_xpath?: XPathInput
  detail_wait_xpath?: XPathInput
  source_language: string
  source_map: Record<string, string>
  content_joiner: string
  default_image_url?: string | null
  date_patterns: string[]
  login_enabled: boolean
  login_username: string
  login_password: string
  playwright_login_url: string
  playwright_login_entry_xpath: string
  playwright_login_username_xpath: string
  playwright_login_password_xpath: string
  playwright_login_submit_xpath: string
  playwright_login_success_xpath: string
  playwright_login_timeout: number
  playwright_headless: boolean
  enable_content_image_placeholder: boolean
  content_root_xpath?: XPathInput
  content_image_xpath?: XPathInput
  content_image_placeholder_template: string
  append_content_image_mapping: boolean
  custom_methods: Record<string, string>
  schedule_type: 'manual' | 'interval' | 'cron'
  cron_expression?: string | null
  interval_seconds?: number | null
  schedule_enabled: boolean
  next_run_at?: string | null
  last_run_at?: string | null
  last_status?: string | null
}

export interface TaskListResult {
  data: CrawlerTask[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface InsertedDataItem {
  article_id: string
  detail_title?: string | null
  detail_title_cn?: string | null
  detail_date?: string | null
  update_time?: string | null
  news_source_name_cn?: string | null
  class_level_1?: string | null
  class_level_2?: string | null
  detail_url?: string | null
  detail_contents?: string | null
  detail_contents_cn?: string | null
}

export interface InsertedDataResult {
  data: InsertedDataItem[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface TaskFormData {
  task_name: string
  description: string
  source_name: string
  prefix: string
  home_url_list: string
  url_xpath: string
  title_xpath: string
  content_xpath: string
  home_date_xpath: string
  date_xpath: string
  image_xpath: string
  detail_image_xpath: string
  url_limit: number
  list_retry_count: number
  list_retry_sleep_seconds: number
  detail_retry_count: number
  detail_retry_sleep_seconds: number
  min_content_length: number
  max_content_length: number
  dedupe_urls: boolean
  home_wait_xpath: string
  detail_wait_xpath: string
  source_language: string
  source_map: string
  content_joiner: string
  default_image_url: string
  date_patterns: string
  login_enabled: boolean
  login_username: string
  login_password: string
  playwright_login_url: string
  playwright_login_entry_xpath: string
  playwright_login_username_xpath: string
  playwright_login_password_xpath: string
  playwright_login_submit_xpath: string
  playwright_login_success_xpath: string
  playwright_login_timeout: number
  playwright_headless: boolean
  enable_content_image_placeholder: boolean
  content_root_xpath: string
  content_image_xpath: string
  content_image_placeholder_template: string
  append_content_image_mapping: boolean
  custom_methods: Record<string, string>
  schedule_type: 'manual' | 'interval' | 'cron'
  cron_expression: string
  interval_seconds: number
  schedule_enabled: boolean
}

export interface TemplateParseResult {
  class_name: string
  attributes: Record<string, any>
  custom_methods: Record<string, string>
  all_method_names: string[]
}
