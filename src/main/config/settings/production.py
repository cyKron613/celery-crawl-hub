from decouple import config

from src.main.config.settings.base import BackendBaseSettings
from src.main.config.settings.environment import Environment


class BackendProdSettings(BackendBaseSettings):
    """
    后台生产环境配置
    """

    DESCRIPTION: str = "Production Environment."
    ENVIRONMENT: Environment = Environment.PRODUCTION
    
    POSTGRES_SCHEMA: str = config("POSTGRES_SCHEMA", cast=str, default="sdc_adm")  # type: ignore
    POSTGRES_SCHEMA_ANOTHER: str = config("POSTGRES_SCHEMA_ANOTHER", cast=str, default="sdc_adm")  # type: ignore
