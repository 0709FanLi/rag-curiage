import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.models.database import engine, Base
from src.models.tables import User
from src.utils.security import get_password_hash
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def init_db():
    async with engine.begin() as conn:
        # ⚠️ 注意：这会删除所有表！仅用于开发初期
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed default user
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("Creating default user 'admin'")
            new_user = User(
                username="admin",
                hashed_password=get_password_hash("admin123")
            )
            session.add(new_user)
            await session.commit()
        else:
            print("User 'admin' already exists")

if __name__ == "__main__":
    asyncio.run(init_db())

