import logging
from typing import Dict, List, Any

from decouple import config
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)
import pathlib
import sys

ROOT_DIR: pathlib.Path = pathlib.Path(
    __file__
).parent.parent.parent.parent.parent.resolve()
sys.path.append(str(ROOT_DIR))



class BackendBaseSettings(BaseSettings):
    """
    后台基础配置
    """

    TITLE: str = "Celery Crawl Hub"
    VERSION: str = "0.0.1"
    DESCRIPTION: str | None = None
    DEBUG: bool = True

    BACKEND_SERVER_HOST: str = config("BACKEND_SERVER_HOST", cast=str, default="0.0.0.0")  # type: ignore
    BACKEND_SERVER_PORT: int = config("BACKEND_SERVER_PORT", cast=int, default=8000)  # type: ignore
    BACKEND_SERVER_WORKERS: int = config("BACKEND_SERVER_WORKERS", cast=int, default=1)  # type: ignore
    API_PREFIX: str = config("API_PREFIX", cast=str, default="/api")  # type: ignore
    DOCS_URL: str = config("DOCS_URL", cast=str, default="/api-doc.html")  # type: ignore
    OPENAPI_URL: str = config("OPENAPI_URL", cast=str, default="/api.json")  # type: ignore
    REDOC_URL: str = config("REDOC_URL", cast=str, default="/api-redoc.html")  # type: ignore
    OPENAPI_PREFIX: str = ""

    DOCS_AUTH_USERNAME: str = config("DOCS_AUTH_USERNAME", cast=str, default="admin")  # type: ignore
    DOCS_AUTH_PASSWORD: str = config("DOCS_AUTH_PASSWORD", cast=str, default="change-me")  # type: ignore

    CELERY_BROKER_URL: str = config("CELERY_BROKER_URL", cast=str, default="redis://localhost:6379/0")  # type: ignore
    CELERY_RESULT_BACKEND: str = config("CELERY_RESULT_BACKEND", cast=str, default="redis://localhost:6379/8")  # type: ignore
    CELERY_BROKER_POOL_LIMIT: int = config("CELERY_BROKER_POOL_LIMIT", cast=int, default=30)  # type: ignore
    CELERY_BROKER_CONNECTION_TIMEOUT: int = config("CELERY_BROKER_CONNECTION_TIMEOUT", cast=int, default=5)  # type: ignore
    CELERY_TIMEZONE: str = config("CELERY_TIMEZONE", cast=str, default="Asia/Shanghai")  # type: ignore
    CELERY_TASK_SOFT_TIME_LIMIT: int = config("CELERY_TASK_SOFT_TIME_LIMIT", cast=int, default=600)  # type: ignore
    CELERY_TASK_TIME_LIMIT: int = config("CELERY_TASK_TIME_LIMIT", cast=int, default=900)  # type: ignore
    CELERY_TASK_ALWAYS_EAGER: bool = config("CELERY_TASK_ALWAYS_EAGER", cast=bool, default=False)  # type: ignore
    CRAWLER_SCHEDULER_SCAN_SECONDS: int = config("CRAWLER_SCHEDULER_SCAN_SECONDS", cast=int, default=60)  # type: ignore
    TRANSLATE_SCHEDULER_SCAN_SECONDS: int = config("TRANSLATE_SCHEDULER_SCAN_SECONDS", cast=int, default=60)  # type: ignore
    CRAWLER_EXECUTION_PREVIEW_LIMIT: int = config("CRAWLER_EXECUTION_PREVIEW_LIMIT", cast=int, default=10)  # type: ignore
    CRAWLER_LOG_TABLE_NAME: str = config("CRAWLER_LOG_TABLE_NAME", cast=str, default="ex_crawl_log")  # type: ignore
    CRAWLER_LOG_DETAIL_TABLE_NAME: str = config("CRAWLER_LOG_DETAIL_TABLE_NAME", cast=str, default="ex_crawl_log_detail")  # type: ignore
    OPENAI_API_KEY: str = config("OPENAI_API_KEY", cast=str, default="")  # type: ignore
    DATABASE_TYPE: str = config("DATABASE_TYPE", cast=str, default="postgresql")  # type: ignore
    CRAWL_TABLE_NAME: str = config("CRAWL_TABLE_NAME", cast=str, default="sdc_test.ex_shipping_information")  # type: ignore
    INSERT_INTO_PROD: bool = config("INSERT_INTO_PROD", cast=bool, default=False)  # type: ignore
    INSERT_INTO_SDC: bool = config("INSERT_INTO_SDC", cast=bool, default=False)  # type: ignore
    CRAWL_ENGINE: str = config("CRAWL_ENGINE", cast=str, default="drissionpage")  # type: ignore
    SDC_TABLE_NAME: str = config("SDC_TABLE_NAME", cast=str, default="sdc_test.ex_shipping_information")  # type: ignore
    SDC_POSTGRES_CONNECT: str = config("SDC_POSTGRES_CONNECT", cast=str, default="postgresql+psycopg2")  # type: ignore
    SDC_POSTGRES_HOST: str = config("SDC_POSTGRES_HOST", cast=str, default="localhost")  # type: ignore
    SDC_POSTGRES_PORT: int = config("SDC_POSTGRES_PORT", cast=int, default=5432)  # type: ignore
    SDC_POSTGRES_DB: str = config("SDC_POSTGRES_DB", cast=str, default="")  # type: ignore
    SDC_POSTGRES_USERNAME: str = config("SDC_POSTGRES_USERNAME", cast=str, default="")  # type: ignore
    SDC_POSTGRES_SCHEMA: str = config("SDC_POSTGRES_SCHEMA", cast=str, default="sdc_bi")  # type: ignore

    # OceanBase（DATABASE_TYPE=oceanbase 时使用）
    OCEANBASE_HOST: str = config("OCEANBASE_HOST", cast=str, default="")  # type: ignore
    OCEANBASE_PORT: int = config("OCEANBASE_PORT", cast=int, default=2883)  # type: ignore
    OCEANBASE_DB: str = config("OCEANBASE_DB", cast=str, default="")  # type: ignore
    OCEANBASE_USERNAME: str = config("OCEANBASE_USERNAME", cast=str, default="")  # type: ignore
    OCEANBASE_PASSWORD: str = config("OCEANBASE_PASSWORD", cast=str, default="")  # type: ignore

    # 生产入库数据库（INSERT_INTO_PROD=true 时使用）
    PROD_DB_HOST: str = config("PROD_DB_HOST", cast=str, default="")  # type: ignore
    PROD_DB_PORT: int = config("PROD_DB_PORT", cast=int, default=3306)  # type: ignore
    PROD_DB_NAME: str = config("PROD_DB_NAME", cast=str, default="")  # type: ignore
    PROD_DB_USERNAME: str = config("PROD_DB_USERNAME", cast=str, default="")  # type: ignore
    PROD_DB_PASSWORD: str = config("PROD_DB_PASSWORD", cast=str, default="")  # type: ignore

    # 微信爬虫
    WECHAT_TOKEN: str = config("WECHAT_TOKEN", cast=str, default="")  # type: ignore
    WECHAT_COOKIE: str = config("WECHAT_COOKIE", cast=str, default="")  # type: ignore

    # 日志
    LOG_LEVEL: str = config("LOG_LEVEL", cast=str, default="INFO")  # type: ignore


    POSTGRES_CONNECT: str = config("POSTGRES_CONNECT", cast=str, default="postgresql+asyncpg")  # type: ignore
    POSTGRES_HOST: str = config("POSTGRES_HOST", cast=str, default="localhost")  # type: ignore
    POSTGRES_PORT: int = config("POSTGRES_PORT", cast=int, default=5432)  # type: ignore
    POSTGRES_DB: str = config("POSTGRES_DB", cast=str, default="crawler_studio")  # type: ignore
    POSTGRES_USERNAME: str = config("POSTGRES_USERNAME", cast=str, default="crawler")  # type: ignore
    POSTGRES_PASSWORD: str = config("POSTGRES_PASSWORD", cast=str, default="change-me")  # type: ignore
    # POSTGRES_SCHEMA: str = config("POSTGRES_SCHEMA", cast=str)  # type: ignore

    # --------------------------------
    #   Production Postgres Config (Another)
    # --------------------------------
    POSTGRES_CONNECT_ANOTHER: str = config("POSTGRES_CONNECT_ANOTHER", cast=str, default="postgresql+asyncpg")  # type: ignore
    POSTGRES_HOST_ANOTHER: str = config("POSTGRES_HOST_ANOTHER", cast=str, default="localhost")  # type: ignore
    POSTGRES_PORT_ANOTHER: int = config("POSTGRES_PORT_ANOTHER", cast=int, default=5432)  # type: ignore
    POSTGRES_DB_ANOTHER: str = config("POSTGRES_DB_ANOTHER", cast=str, default="crawler_studio")  # type: ignore
    POSTGRES_USERNAME_ANOTHER: str = config("POSTGRES_USERNAME_ANOTHER", cast=str, default="crawler")  # type: ignore
    POSTGRES_PASSWORD_ANOTHER: str = config("POSTGRES_PASSWORD_ANOTHER", cast=str, default="change-me")  # type: ignore
    # POSTGRES_SCHEMA_ANOTHER: str = config("POSTGRES_SCHEMA_ANOTHER", cast=str)  # type: ignore

    
    DB_POOL_SIZE: int = config("DB_POOL_SIZE", cast=int, default=5)  # type: ignore
    DB_POOL_OVERFLOW: int = config("DB_POOL_OVERFLOW", cast=int, default=10)  # type: ignore
    DB_POOL_RECYCLE: int = config("DB_POOL_RECYCLE", cast=int, default=1800)  # type: ignore
    DB_POOL_TIMEOUT: int = config("DB_POOL_TIMEOUT", cast=int, default=30)  # type: ignore
    DB_POOL_RESET_ON_RETURN: str = config("DB_POOL_RESET_ON_RETURN", cast=str, default="rollback")  # type: ignore
    DB_RETRY_ATTEMPTS: int = config("DB_RETRY_ATTEMPTS", cast=int, default=3)  # type: ignore
    DB_RETRY_DELAY: float = config("DB_RETRY_DELAY", cast=float, default=0.5)  # type: ignore
    DB_RETRY_BACKOFF: float = config("DB_RETRY_BACKOFF", cast=float, default=2.0)  # type: ignore

    IS_DB_ECHO_LOG: bool = config("IS_DB_ECHO_LOG", cast=bool, default=False)  # type: ignore


    # 修改REDIS_PORT的处理方式
    def parse_redis_port(value):
        if value and "://" in value:
            # 如果是完整的连接字符串，提取端口部分
            return int(value.split(":")[-1])
        return int(value)
        
    # redis
    PROD_REDIS_HOST: str = config("PROD_REDIS_HOST", cast=str, default="localhost")  # type: ignore
    PROD_REDIS_PORT: int = config("PROD_REDIS_PORT", cast=parse_redis_port, default=6379)  # type: ignore
    PROD_REDIS_PASSWORD: str = config("PROD_REDIS_PASSWORD", cast=str, default="")  # type: ignore
    PROD_REDIS_DB: int = config("PROD_REDIS_DB", cast=int, default=0)  # type: ignore
    PROD_REDIS_CLUSTER: bool = config("PROD_REDIS_CLUSTER", cast=bool, default=False)  # type: ignore
    PROD_REDIS_NODES: str = config("PROD_REDIS_NODES", cast=str, default="")  # type: ignore

    TEST_REDIS_HOST: str = config("TEST_REDIS_HOST", cast=str, default="localhost")  # type: ignore
    TEST_REDIS_PORT: int = config("TEST_REDIS_PORT", cast=parse_redis_port, default=6379)  # type: ignore
    TEST_REDIS_PASSWORD: str = config("TEST_REDIS_PASSWORD", cast=str, default="")  # type: ignore
    TEST_REDIS_DB: int = config("TEST_REDIS_DB", cast=int, default=0)  # type: ignore
    TEST_REDIS_CLUSTER: bool = config("TEST_REDIS_CLUSTER", cast=bool, default=False)  # type: ignore

    # Pydantic v2 `BaseSettings` 会对 `List[str]` 字段做 JSON 解析，与逗号分隔
    # 字符串不兼容；这里用纯字符串保存原始值，再通过 property 拆分。
    ALLOWED_ORIGINS_RAW: str = config(
        "ALLOWED_ORIGINS",
        cast=str,
        default="http://127.0.0.1:8111,http://localhost:7860",
    )  # type: ignore
    ALLOWED_METHODS: List[str] = ["*"]
    ALLOWED_HEADERS: List[str] = ["*"]

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return [item.strip() for item in self.ALLOWED_ORIGINS_RAW.split(",") if item.strip()]

    LOGGING_LEVEL: int = logging.INFO


    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        validate_assignment=True,
        case_sensitive=True,
    )


    @property
    def gset_backend_app_attributes(self) -> Dict[str, Any]:
        """
        algo backend template application necessary variable.
        """
        return {
            "title": self.TITLE,
            "version": self.VERSION,
            "debug": self.DEBUG,
            "description": self.DESCRIPTION,
            "docs_url": self.DOCS_URL,
            "openapi_url": self.OPENAPI_URL,
            "redoc_url": self.REDOC_URL,
            "openapi_prefix": self.OPENAPI_PREFIX,
            "api_prefix": self.API_PREFIX,
        }
