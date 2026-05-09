import threading
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from loguru import logger

# 导入项目配置
from src.main.config.manager import settings

Base = declarative_base()


class ProdDatabaseManager:
    """生产数据库连接管理器，单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ProdDatabaseManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._engine = None
            self._session_factory = None
            self._scoped_session = None
            self._initialized = True
    
    def _build_db_url(self) -> str:
        """构建数据库连接URL"""
        username = quote_plus(settings.PROD_DB_USERNAME)
        password = quote_plus(settings.PROD_DB_PASSWORD)
        return f"mysql+pymysql://{username}:{password}@{settings.PROD_DB_HOST}:{settings.PROD_DB_PORT}/{settings.PROD_DB_NAME}"
    
    def init_database(self):
        """初始化数据库连接"""
        if self._engine is not None:
            return
            
        try:
            # 获取数据库连接URL
            db_url = self._build_db_url()
            
            # 连接池配置
            pool_config = {
                "poolclass": QueuePool,
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_POOL_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_reset_on_return": settings.DB_POOL_RESET_ON_RETURN,
                "echo": settings.IS_DB_ECHO_LOG,
                "pool_pre_ping": True,
                "connect_args": {
                    "charset": "utf8mb4",
                    "connect_timeout": 5,
                    "read_timeout": 30,
                    "write_timeout": 30,
                },
            }
            
            # 创建带连接池的引擎
            self._engine = create_engine(db_url, **pool_config)
            
            # 创建会话工厂
            self._session_factory = sessionmaker(bind=self._engine)
            
            # 创建线程安全的scoped session
            self._scoped_session = scoped_session(self._session_factory)
            
            # logger.info(f"生产数据库连接池初始化成功: {db_url}") # Avoid logging credentials
            logger.info("生产数据库连接池初始化成功")
            
        except Exception as e:
            logger.error(f"生产数据库连接初始化失败: {e}")
            # 不抛出异常，避免影响主任务流程
            self._engine = None
            self._session_factory = None
            self._scoped_session = None

    def get_session(self):
        """从连接池获取一个会话"""
        if self._scoped_session is None:
            raise RuntimeError("生产数据库连接未初始化，请先调用init_database()")
        
        return self._scoped_session()
    
    def close_session(self, session):
        """关闭会话，将连接返回到连接池"""
        if session:
            session.close()

    def dispose(self):
        """释放所有数据库连接"""
        if self._scoped_session:
            self._scoped_session.remove()
        if self._engine:
            self._engine.dispose()
        logger.info("生产数据库连接池已释放")

# 创建全局生产数据库管理器实例并初始化
prod_db = ProdDatabaseManager()
prod_db.init_database()
