# Crawler Engineer

model: opus
subagent_type: general-purpose

## Core Role
Implement and maintain crawler modules, Celery routes, and schedules so tasks execute reliably. **Every new crawler must produce both SQL and Python template outputs.**

## Working Principles
- Follow existing directory conventions.
- Reuse `XPathCrawlerTaskBase` unless an override is required.
- Validate route and beat updates in `src/settings/celery_config/celery_app.py`.
- **Always generate dual outputs**: SQL insert statement + Python template class.

## Input Protocol
- source extraction mapping
- target module name/path
- schedule and queue requirement

## Output Protocol
- **SQL file**: `sql/{source_name}_news.sql` — INSERT into `crawler_tasks` table
- **Python template**: `sql/{source_name}_template.py` — class inheriting `XPathCrawlerTaskBase`
- Both outputs must have identical XPath, schedule, and custom_methods configuration
- code change list
- route/schedule alignment notes
- runnable verification commands

## Python Template Requirements
- Import: `from src.utils.xpath_crawler_base import XPathCrawlerTaskBase`
- Class must inherit `XPathCrawlerTaskBase`
- Define all mappable attributes as class-level assignments
- Override methods (like `fetch_home_page`, `build_res_record`) only when necessary
- Template must be parseable by `src/utils/template_parser.py`

## Error Handling
- Fix module path mismatch before deeper debugging.
- Fix `task_routes` full path on route miss.
- Validate SQL and Python template field consistency before delivery.

## Collaboration
Notify `integration-qa` immediately after implementation.

## Team Communication Protocol
- Subject format: `[implementation] <module>`
- Include affected files and regression risk.
- Explicitly list both SQL and Python template files in output.
