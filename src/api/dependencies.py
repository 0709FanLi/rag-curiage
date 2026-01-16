from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.config.settings import settings
from src.models.database import get_db
from src.models.tables import User
from src.services.dashboard_cache_service import DashboardCacheService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@lru_cache(maxsize=1)
def get_dashboard_cache_service() -> DashboardCacheService:
    """Get a singleton dashboard cache service (process-local)."""
    return DashboardCacheService(ttl_seconds=30.0)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception as e:
        # 捕获所有 JWT 相关异常（包括过期）
        import logging
        logging.error(f"Token validation error: {e}")
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
