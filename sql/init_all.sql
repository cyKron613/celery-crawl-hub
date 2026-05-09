-- One-shot bootstrap for local / fresh databases.
-- Equivalent to the order Docker Compose loads files from
-- /docker-entrypoint-initdb.d on a fresh Postgres container.
--
-- Usage:
--   psql "$DATABASE_URL" -f sql/init_all.sql
--
-- All bundled SQL assumes the default schema `sdc_test`. If you change
-- POSTGRES_SCHEMA, edit the SQL files (search/replace `sdc_test`) before
-- running this script.

\echo '==> Loading crawler_tasks.sql'
\i sql/crawler_tasks.sql

\echo '==> Loading ex_crawl_log.sql'
\i sql/ex_crawl_log.sql

\echo '==> Loading ex_shipping_information.sql'
\i sql/ex_shipping_information.sql
