"""邮箱验证码（OTP）服务。

职责：
- 生成验证码（仅返回明文用于发送邮件，不落库明文）
- 频率限制（同邮箱冷却、每小时次数上限）
- 持久化（hash、过期时间、用途、发送 IP）
- 校验并标记使用
"""

from __future__ import annotations

import hmac
import logging
import secrets
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models.tables import EmailVerificationCode

logger = logging.getLogger("healthy_rag")


class EmailOtpError(Exception):
    """邮箱验证码服务异常。"""


def _hash_code(*, email: str, purpose: str, code: str) -> str:
    """对验证码做 HMAC-SHA256 hash（避免明文入库）。"""
    key = (settings.SECRET_KEY or "").encode("utf-8")
    msg = f"{email}|{purpose}|{code}".encode("utf-8")
    return hmac.new(key, msg=msg, digestmod=sha256).hexdigest()


class EmailOtpService:
    """邮箱验证码服务。"""

    async def create_and_store_code(
        self,
        *,
        db: AsyncSession,
        email: str,
        purpose: str,
        send_ip: Optional[str],
    ) -> str:
        """生成并入库验证码（返回明文用于发送邮件）。"""
        now = datetime.utcnow()

        cooldown_seconds = int(settings.EMAIL_OTP_COOLDOWN_SECONDS)
        max_per_hour = int(settings.EMAIL_OTP_MAX_PER_HOUR)
        expire_minutes = int(settings.EMAIL_OTP_EXPIRE_MINUTES)

        # 1) 冷却：同邮箱+用途，60s 内不允许重复发送
        cooldown_since = now - timedelta(seconds=cooldown_seconds)
        recent_stmt = (
            select(EmailVerificationCode)
            .where(EmailVerificationCode.email == email)
            .where(EmailVerificationCode.purpose == purpose)
            .where(EmailVerificationCode.created_at >= cooldown_since)
            .order_by(desc(EmailVerificationCode.created_at))
            .limit(1)
        )
        recent = (await db.execute(recent_stmt)).scalar_one_or_none()
        if recent:
            raise EmailOtpError(f"发送过于频繁，请 {cooldown_seconds}s 后再试")

        # 2) 每小时上限
        hour_since = now - timedelta(hours=1)
        count_stmt = (
            select(func.count())
            .select_from(EmailVerificationCode)
            .where(EmailVerificationCode.email == email)
            .where(EmailVerificationCode.purpose == purpose)
            .where(EmailVerificationCode.created_at >= hour_since)
        )
        count = int((await db.execute(count_stmt)).scalar() or 0)
        if count >= max_per_hour:
            raise EmailOtpError("发送次数过多，请稍后再试")

        # 3) 生成 6 位验证码
        code = str(secrets.randbelow(1_000_000)).zfill(6)
        code_hash = _hash_code(email=email, purpose=purpose, code=code)
        expires_at = now + timedelta(minutes=expire_minutes)

        record = EmailVerificationCode(
            email=email,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=expires_at,
            used_at=None,
            send_ip=send_ip,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        logger.info(
            "Email OTP created email=%s purpose=%s id=%s expires_at=%s",
            email,
            purpose,
            record.id,
            record.expires_at,
        )
        return code

    async def verify_and_consume(
        self,
        *,
        db: AsyncSession,
        email: str,
        purpose: str,
        code: str,
    ) -> None:
        """校验验证码并标记 used_at。"""
        now = datetime.utcnow()
        code_hash = _hash_code(email=email, purpose=purpose, code=code)

        stmt = (
            select(EmailVerificationCode)
            .where(EmailVerificationCode.email == email)
            .where(EmailVerificationCode.purpose == purpose)
            .where(EmailVerificationCode.code_hash == code_hash)
            .order_by(desc(EmailVerificationCode.created_at))
            .limit(1)
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            raise EmailOtpError("验证码错误")
        if record.used_at is not None:
            raise EmailOtpError("验证码已使用")
        if record.expires_at < now:
            raise EmailOtpError("验证码已过期")

        record.used_at = now
        db.add(record)
        await db.commit()


email_otp_service = EmailOtpService()


