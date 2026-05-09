from decouple import config

from src.main.config.settings.base import BackendBaseSettings
from src.main.config.settings.environment import Environment


class BackendDevSettings(BackendBaseSettings):
    """
    后台测试环境配置
    """

    DESCRIPTION: str = "Development Environment."
    DEBUG: bool = True
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    POSTGRES_SCHEMA: str = config("POSTGRES_SCHEMA", cast=str, default="sdc_test")  # type: ignore
    POSTGRES_SCHEMA_ANOTHER: str = config("POSTGRES_SCHEMA_ANOTHER", cast=str, default="sdc_test")  # type: ignore



