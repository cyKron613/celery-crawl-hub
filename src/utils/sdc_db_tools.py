import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from loguru import logger

# 导入项目配置
from src.main.config.manager import settings

Base = declarative_base()


class SDCDatabaseManager:
    """SDC数据库连接管理器，单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SDCDatabaseManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._engine = None
            self._session_factory = None
            self._scoped_session = None
            self._initialized = True
    
    def _build_postgresql_url(self) -> str:
        """构建PostgreSQL连接URL"""
        return f"{settings.SDC_POSTGRES_CONNECT}://{settings.SDC_POSTGRES_USERNAME}:{settings.SDC_POSTGRES_PASSWORD}@{settings.SDC_POSTGRES_HOST}:{settings.SDC_POSTGRES_PORT}/{settings.SDC_POSTGRES_DB}"
    
    def init_database(self):
        """初始化数据库连接"""
        if self._engine is not None:
            return
            
        try:
            # 获取数据库连接URL
            db_url = self._build_postgresql_url()
            
            # 连接池配置
            pool_config = {
                "poolclass": QueuePool,
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_POOL_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_reset_on_return": settings.DB_POOL_RESET_ON_RETURN,
                "echo": settings.IS_DB_ECHO_LOG,
            }
            
            # 创建带连接池的引擎
            self._engine = create_engine(db_url, **pool_config)
            
            # 创建会话工厂
            self._session_factory = sessionmaker(bind=self._engine)
            
            # 创建线程安全的scoped session
            self._scoped_session = scoped_session(self._session_factory)
            
            logger.info(f"SDC数据库连接池初始化成功: {db_url}")
            
        except Exception as e:
            logger.error(f"SDC数据库连接初始化失败: {e}")
            raise

    def get_session(self):
        """从连接池获取一个会话"""
        if self._scoped_session is None:
            raise RuntimeError("SDC数据库连接未初始化，请先调用init_database()")
        
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
        logger.info("SDC数据库连接池已释放")

# 创建全局SDC数据库管理器实例并初始化
sdc_db = SDCDatabaseManager()
sdc_db.init_database()
