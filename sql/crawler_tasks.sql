CREATE SCHEMA IF NOT EXISTS sdc_test;

CREATE TABLE IF NOT EXISTS sdc_test.crawler_tasks (
    id UUID PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    source_name VARCHAR(100) NOT NULL,
    prefix VARCHAR(500),
    home_url_list JSONB NOT NULL,
    url_xpath JSONB NOT NULL,
    title_xpath JSONB NOT NULL,
    content_xpath JSONB NOT NULL,
    home_date_xpath JSONB,
    date_xpath JSONB,
    image_xpath JSONB,
    detail_image_xpath JSONB,
    url_limit INTEGER NOT NULL DEFAULT 10,
    list_retry_count INTEGER NOT NULL DEFAULT 1,
    list_retry_sleep_seconds INTEGER NOT NULL DEFAULT 3,
    detail_retry_count INTEGER NOT NULL DEFAULT 0,
    detail_retry_sleep_seconds INTEGER NOT NULL DEFAULT 2,
    min_content_length INTEGER NOT NULL DEFAULT 0,
    max_content_length INTEGER NOT NULL DEFAULT 0,
    dedupe_urls BOOLEAN NOT NULL DEFAULT FALSE,
    home_wait_xpath JSONB,
    detail_wait_xpath JSONB,
    source_language VARCHAR(20) NOT NULL DEFAULT 'auto',
    source_map JSONB,
    content_joiner VARCHAR(20) NOT NULL DEFAULT ' ',
    default_image_url TEXT,
    date_patterns JSONB,
    schedule_type VARCHAR(20) NOT NULL DEFAULT 'manual',
    cron_expression VARCHAR(120),
    interval_seconds INTEGER,
    schedule_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    last_status VARCHAR(20) NOT NULL DEFAULT 'idle',
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sdc_test.crawler_task_executions (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES sdc_test.crawler_tasks(id) ON DELETE CASCADE,
    trigger_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    celery_task_id VARCHAR(100),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    result_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    result_preview JSONB,
    inserted_article_ids JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE sdc_test.crawler_task_executions
ADD COLUMN IF NOT EXISTS inserted_article_ids JSONB;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS home_wait_xpath JSONB;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS min_content_length INTEGER NOT NULL DEFAULT 0;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS max_content_length INTEGER NOT NULL DEFAULT 0;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS custom_methods JSONB;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS login_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS login_username VARCHAR(200) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS login_password VARCHAR(200) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_login_url VARCHAR(500) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_login_entry_xpath VARCHAR(500) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_login_username_xpath VARCHAR(500) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_login_password_xpath VARCHAR(500) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_login_submit_xpath VARCHAR(500) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_login_success_xpath VARCHAR(500) NOT NULL DEFAULT '';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_login_timeout INTEGER NOT NULL DEFAULT 60;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS playwright_headless BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS enable_content_image_placeholder BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS content_root_xpath JSONB;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS content_image_xpath JSONB;

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS content_image_placeholder_template VARCHAR(200) NOT NULL DEFAULT '![图片{index}]({url})';

ALTER TABLE sdc_test.crawler_tasks
ADD COLUMN IF NOT EXISTS append_content_image_mapping BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_crawler_tasks_schedule_enabled ON sdc_test.crawler_tasks(schedule_enabled, next_run_at);
CREATE INDEX IF NOT EXISTS idx_crawler_task_executions_task_id ON sdc_test.crawler_task_executions(task_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawler_task_executions_celery_task_id ON sdc_test.crawler_task_executions(celery_task_id);