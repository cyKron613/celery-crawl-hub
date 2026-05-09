
import threading
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from loguru import logger

# 导入项目配置
from src.main.config.manager import settings

Base = declarative_base()


class DatabaseManager:
    """数据库连接管理器，单例模式，使用连接池，支持PostgreSQL和OceanBase"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._engine = None
            self._session_factory = None
            self._scoped_session = None
            self._initialized = True
    
    def _build_postgresql_url(self) -> str:
        """构建PostgreSQL同步连接URL。

        ``settings.POSTGRES_CONNECT`` 可能被配置为异步驱动（如 ``postgresql+asyncpg``）
        供 FastAPI 的 async ORM 使用。这里使用的是同步 ``create_engine`` + ``QueuePool``，
        需要强制回退到同步驱动，避免 ``Pool class QueuePool cannot be used with asyncio engine``。
        """
        connect = settings.POSTGRES_CONNECT
        if "+asyncpg" in connect:
            connect = connect.replace("+asyncpg", "+psycopg2")
        elif connect == "postgresql":
            connect = "postgresql+psycopg2"
        return f"{connect}://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    
    def _build_oceanbase_url(self) -> str:
        """构建OceanBase连接URL"""
        # OceanBase使用MySQL协议，连接格式：mysql+pymysql://user:password@host:port/database
        # 注意：用户名和密码中的特殊字符需要正确编码
        import urllib.parse
        username = urllib.parse.quote_plus(settings.OCEANBASE_USERNAME)
        password = urllib.parse.quote_plus(settings.OCEANBASE_PASSWORD)
        return f"mysql+pymysql://{username}:{password}@{settings.OCEANBASE_HOST}:{settings.OCEANBASE_PORT}/{settings.OCEANBASE_DB}"
    
    def _get_database_url(self, database_url: Optional[str] = None) -> str:
        """获取数据库连接URL"""
        if database_url:
            return database_url
            
        # 根据配置的数据库类型选择相应的连接URL
        if settings.DATABASE_TYPE.lower() == "oceanbase":
            # 检查OceanBase配置是否完整
            if not all([settings.OCEANBASE_HOST, settings.OCEANBASE_USERNAME, settings.OCEANBASE_PASSWORD, settings.OCEANBASE_DB]):
                raise ValueError("OceanBase配置不完整，请检查OCEANBASE_HOST, OCEANBASE_USERNAME, OCEANBASE_PASSWORD, OCEANBASE_DB配置项")
            return self._build_oceanbase_url()
        else:
            # 默认使用PostgreSQL
            return self._build_postgresql_url()
    
    def init_database(self, database_url: Optional[str] = None):
        """初始化数据库连接"""
        if self._engine is not None:
            return
            
        try:
            # 获取数据库连接URL
            db_url = self._get_database_url(database_url)
            
            # 根据数据库类型调整连接池配置
            pool_config = {
                "poolclass": QueuePool,
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_POOL_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_reset_on_return": settings.DB_POOL_RESET_ON_RETURN,
                "echo": settings.IS_DB_ECHO_LOG,
                "pool_pre_ping": True,
            }
            
            # OceanBase可能需要特殊的连接参数
            if settings.DATABASE_TYPE.lower() == "oceanbase":
                # 添加OceanBase特定的连接参数
                pool_config.update({
                    "connect_args": {
                        "charset": "utf8mb4",
                        # "autocommit": True,
                        "connect_timeout": 5,
                        "read_timeout": 30,
                        "write_timeout": 30,
                    }
                })
            
            # 创建带连接池的引擎
            self._engine = create_engine(db_url, **pool_config)
            
            # 创建会话工厂
            self._session_factory = sessionmaker(bind=self._engine)
            
            # 创建线程安全的scoped session
            self._scoped_session = scoped_session(self._session_factory)
            
            logger.info(f"{settings.DATABASE_TYPE.upper()}数据库连接池初始化成功: {db_url}")
            
        except Exception as e:
            logger.error(f"数据库连接初始化失败: {e}")
            raise
    
    def get_session(self):
        """从连接池获取一个会话"""
        self._ensure_initialized()
        return self._scoped_session()  # type: ignore[union-attr]

    def _ensure_initialized(self):
        """确保连接池已初始化（懒加载）"""
        if self._scoped_session is None:
            self.init_database()
    
    def close_session(self, session):
        """关闭会话，将连接返回到连接池"""
        if session:
            session.close()
    
    def test_connection(self) -> bool:
        """测试数据库连接是否正常"""
        if self._engine is None:
            logger.warning("数据库连接未初始化")
            return False
        
        try:
            with self._engine.connect() as conn:
                # 根据数据库类型执行不同的测试语句
                if settings.DATABASE_TYPE.lower() == "oceanbase":
                    # OceanBase使用MySQL语法
                    conn.execute(text("SELECT 1"))
                else:
                    # PostgreSQL语法
                    conn.execute(text("SELECT 1"))
                
            logger.info("数据库连接测试成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        return {
            "database_type": settings.DATABASE_TYPE,
            "is_connected": self._engine is not None,
            "connection_url": self._get_database_url() if self._engine else None,
        }
    
    def dispose(self):
        """释放所有数据库连接"""
        if self._scoped_session:
            self._scoped_session.remove()
        if self._engine:
            self._engine.dispose()
        logger.info("数据库连接池已释放")


# 创建全局数据库管理器实例
db_manager = DatabaseManager()

# 初始化数据库连接（可以在应用启动时调用）
def init_database_connection(database_url: Optional[str] = None):
    """初始化数据库连接"""
    db_manager.init_database(database_url)


# 关闭数据库连接（可以在应用退出时调用）
def close_database_connection():
    """关闭数据库连接"""
    db_manager.dispose()


# 测试数据库连接
def test_database_connection() -> bool:
    """测试数据库连接"""
    return db_manager.test_connection()


# 获取数据库信息
def get_database_info() -> Dict[str, Any]:
    """获取数据库信息"""
    return db_manager.get_database_info()


# 全局同步数据库管理器实例。
# 模块导入时即建立连接池，便于直接通过 ``std_db._scoped_session()`` 使用；
# 数据库暂不可用时仅记录错误，不抛出，避免 worker 启动崩溃，后续访问会通过
# ``DatabaseManager.get_session()`` 触发懒加载重试。
std_db = DatabaseManager()
try:
    std_db.init_database()
except Exception as exc:
    logger.warning(f"std_db 模块级初始化失败（将延迟到首次访问时重试）: {exc}")
