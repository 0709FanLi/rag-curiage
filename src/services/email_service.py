"""邮件发送服务（SMTP）。

该模块只负责“发送邮件”这一件事，具体验证码生成与频控在更高层服务实现。
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Optional

from src.config.settings import settings

logger = logging.getLogger("healthy_rag")


class EmailServiceError(Exception):
    """邮件发送异常。"""


class EmailService:
    """基于 SMTP 的邮件发送服务。"""

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_addr: Optional[str] = None,
        starttls: Optional[bool] = None,
    ) -> None:
        self._host = host or settings.SMTP_HOST
        self._port = port or settings.SMTP_PORT
        self._username = username or settings.SMTP_USERNAME
        self._password = password or settings.SMTP_PASSWORD
        self._from_addr = from_addr or settings.SMTP_FROM or self._username
        self._ssl = settings.SMTP_SSL
        self._starttls = settings.SMTP_STARTTLS if starttls is None else starttls

    def _validate(self) -> None:
        if not self._host:
            raise EmailServiceError("SMTP_HOST 未配置")
        if not self._port:
            raise EmailServiceError("SMTP_PORT 未配置")
        if not self._username:
            raise EmailServiceError("SMTP_USERNAME 未配置")
        if not self._password:
            raise EmailServiceError("SMTP_PASSWORD 未配置")
        if not self._from_addr:
            raise EmailServiceError("SMTP_FROM 未配置")

    async def send_text_email(
        self,
        *,
        to_addr: str,
        subject: str,
        body_text: str,
    ) -> None:
        """发送纯文本邮件。

        Args:
            to_addr: 收件人邮箱
            subject: 邮件主题
            body_text: 邮件正文（纯文本）

        Raises:
            EmailServiceError: SMTP 未配置或发送失败
        """
        self._validate()

        try:
            import aiosmtplib
        except Exception as exc:  # pragma: no cover
            raise EmailServiceError("缺少依赖 aiosmtplib，请先安装") from exc

        message = EmailMessage()
        message["From"] = self._from_addr
        message["To"] = to_addr
        message["Subject"] = subject
        message.set_content(body_text)

        logger.info("SMTP sending email to=%s subject=%s", to_addr, subject)

        try:
            # 使用 aiosmtplib.send 统一处理连接生命周期，避免服务端断开导致的未回收 Future 警告
            await aiosmtplib.send(
                message,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                use_tls=self._ssl,
                start_tls=(self._starttls if not self._ssl else False),
                timeout=20,
            )
        except Exception as exc:
            logger.exception("SMTP send failed to=%s", to_addr)
            raise EmailServiceError("邮件发送失败") from exc


email_service = EmailService()


