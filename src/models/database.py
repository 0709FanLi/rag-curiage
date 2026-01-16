import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config.settings import settings

logger = logging.getLogger(__name__)

# 创建异步引擎
engine_kwargs = {
    "echo": True,  # 开发模式下打印 SQL（生产可通过日志级别控制）
    "future": True,
}

if settings.DATABASE_URL.startswith("sqlite+aiosqlite"):
    # SQLite 单写入锁：增加 busy timeout，降低高并发下的 'database is locked'
    engine_kwargs["connect_args"] = {"timeout": 30}

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

if settings.DATABASE_URL.startswith("sqlite+aiosqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
        """为 SQLite 设置更适合并发读写的 PRAGMA（WAL + busy_timeout）。"""
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()
        except Exception as exc:
            logger.warning("设置SQLite PRAGMA失败: %s", exc)

# 创建异步 Session 工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """依赖注入获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

