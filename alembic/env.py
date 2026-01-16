"""Alembic 环境配置。

说明：
- 生产使用 docker-compose 传入 DATABASE_URL（sqlite+aiosqlite:///healthy.db）。
- Alembic 使用同步引擎执行迁移，需要将 async URL 转换为 sync URL。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Optional

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL, make_url

# Ensure project root is on sys.path so `import src...` works in containers.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Alembic Config object
config = context.config

# Configure Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_database_url() -> str:
    """获取数据库 URL（优先环境变量，其次读取应用 settings）。"""
    env_url = os.getenv('DATABASE_URL')
    if env_url:
        return env_url
    # Fallback: import settings
    from src.config.settings import settings  # noqa: WPS433 (runtime import)

    return settings.DATABASE_URL


def _to_sync_url(database_url: str) -> str:
    """将 async SQLAlchemy URL 转换为 sync URL（用于 Alembic）。"""
    url: URL = make_url(database_url)
    drivername = url.drivername
    if drivername.startswith('sqlite+aiosqlite'):
        url = url.set(drivername='sqlite')
    elif drivername.startswith('postgresql+asyncpg'):
        url = url.set(drivername='postgresql')
    return str(url)


def _load_target_metadata():
    """加载全部模型，确保 Base.metadata 包含所有表。"""
    from src.models.database import Base  # noqa: WPS433 (runtime import)

    # 关键：导入 models 以注册表到 metadata
    import src.models.tables  # noqa: F401,WPS433

    return Base.metadata


target_metadata = _load_target_metadata()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    database_url = _to_sync_url(_get_database_url())
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    database_url = _to_sync_url(_get_database_url())

    configuration = config.get_section(config.config_ini_section) or {}
    configuration['sqlalchemy.url'] = database_url

    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


