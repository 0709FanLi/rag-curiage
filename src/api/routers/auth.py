from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from src.models.database import get_db
from src.models.tables import User
from src.utils.security import verify_password, create_access_token, get_password_hash
from pydantic import BaseModel, field_validator, model_validator
from src.services.email_service import email_service, EmailServiceError
from src.services.email_otp_service import email_otp_service, EmailOtpError
import re
import logging
router = APIRouter()
logger = logging.getLogger("healthy_rag")

_PHONE_PATTERN = re.compile(r"^1\d{10}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_phone(value: str) -> bool:
    return bool(_PHONE_PATTERN.match(value or ""))


def _looks_like_email(value: str) -> bool:
    return bool(_EMAIL_PATTERN.match(value or ""))


def _mask_email(email: Optional[str]) -> str:
    if not email:
        return ""
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    prefix = local[:2] if len(local) >= 2 else local
    return f"{prefix}***@{domain}"


def _mask_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    if len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


class Token(BaseModel):
    """登录响应模型。"""

    access_token: str
    token_type: str
    username: str
    user_id: int


class RegisterRequest(BaseModel):
    """注册请求模型（兼容旧 Web：username/password；移动端：email+phone+email_code+password）。"""

    # Legacy
    username: Optional[str] = None

    # Mobile
    email: Optional[str] = None
    phone: Optional[str] = None
    email_code: Optional[str] = None
    purpose: str = "register"

    # Shared
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^[a-zA-Z0-9]{3,20}$", v):
            raise ValueError("用户名只能包含英文字母和数字，长度 3-20 位")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _looks_like_email(v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _looks_like_phone(v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("email_code")
    @classmethod
    def validate_email_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^\d{6}$", v):
            raise ValueError("验证码格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度至少 6 位")
        return v

    @model_validator(mode="after")
    def validate_mode(self) -> "RegisterRequest":
        # 两种模式二选一
        if self.username:
            return self
        if self.email and self.phone and self.email_code:
            return self
        raise ValueError("注册参数不完整：请填写 username 或 email+phone+email_code")


class RegisterResponse(BaseModel):
    """注册响应模型。"""

    message: str
    username: str
    user_id: int


class EmailCodeRequest(BaseModel):
    """发送邮箱验证码请求。"""

    email: str
    purpose: str = "register"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _looks_like_email(v):
            raise ValueError("邮箱格式不正确")
        return v


class EmailCodeResponse(BaseModel):
    """发送邮箱验证码响应。"""

    message: str


@router.post("/email/code", response_model=EmailCodeResponse)
async def send_email_code(
    request: EmailCodeRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """发送邮箱验证码（用于注册）。"""
    send_ip = None
    try:
        send_ip = http_request.client.host if http_request.client else None
    except Exception:
        send_ip = None

    try:
        code = await email_otp_service.create_and_store_code(
            db=db,
            email=request.email,
            purpose=request.purpose,
            send_ip=send_ip,
        )
        await email_service.send_text_email(
            to_addr=request.email,
            subject="Healthy RAG 邮箱验证码",
            body_text=(
                "您的验证码为："
                f"{code}\n\n"
                "验证码仅用于身份验证，请勿泄露给他人。"
            ),
        )
    except EmailOtpError as exc:
        logger.warning(
            "Send email OTP rejected email=%s purpose=%s ip=%s err=%s",
            request.email,
            request.purpose,
            send_ip,
            exc,
        )
        raise HTTPException(status_code=429, detail=str(exc))
    except EmailServiceError as exc:
        # Don't log OTP code; only log destination and reason.
        logger.exception(
            "Send email OTP failed email=%s purpose=%s ip=%s",
            request.email,
            request.purpose,
            send_ip,
        )
        raise HTTPException(status_code=500, detail=str(exc))

    return {"message": "验证码已发送到邮箱"}


@router.post("/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册接口。

    Args:
        request: 注册请求数据
        db: 数据库会话

    Returns:
        注册成功的响应

    Raises:
        HTTPException: 用户名已存在
    """
    try:
        # Legacy: username/password
        if request.username:
            if _looks_like_phone(request.username):
                existing_phone_user = (
                    await db.execute(
                        select(User).where(User.phone == request.username)
                    )
                ).scalar_one_or_none()
                if existing_phone_user:
                    logger.info(
                        "Register rejected (phone exists) username=%s",
                        _mask_phone(request.username),
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="手机号已注册，请直接登录或使用找回密码",
                    )

            result = await db.execute(
                select(User).where(User.username == request.username)
            )
            existing_user = result.scalar_one_or_none()
            if existing_user:
                logger.info(
                    "Register rejected (username exists) username=%s",
                    request.username,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户名已存在",
                )

            hashed_password = get_password_hash(request.password)
            new_user = User(
                username=request.username,
                hashed_password=hashed_password,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            logger.info(
                "Register success (legacy) user_id=%s username=%s",
                new_user.id,
                new_user.username,
            )
            return {
                "message": "注册成功",
                "username": new_user.username,
                "user_id": new_user.id,
            }

        # Mobile: email + phone + email_code + password
        assert request.email is not None
        assert request.phone is not None
        assert request.email_code is not None

        # 检查 email / phone / username(email) 是否已存在
        username_for_user = request.email
        stmt = select(User).where(
            or_(
                User.username == username_for_user,
                User.email == request.email,
                User.phone == request.phone,
            )
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            logger.info(
                "Register rejected (account exists) email=%s phone=%s",
                _mask_email(request.email),
                _mask_phone(request.phone),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="账号已存在",
            )

        # 验证验证码（放在“账号已存在”校验之后，避免注册失败仍消耗验证码）
        try:
            await email_otp_service.verify_and_consume(
                db=db,
                email=request.email,
                purpose=request.purpose,
                code=request.email_code,
            )
        except EmailOtpError as exc:
            logger.warning(
                "Register rejected (otp invalid) email=%s purpose=%s err=%s",
                _mask_email(request.email),
                request.purpose,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        hashed_password = get_password_hash(request.password)
        new_user = User(
            username=username_for_user,
            email=request.email,
            phone=request.phone,
            hashed_password=hashed_password,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(
            "Register success (mobile) user_id=%s email=%s phone=%s",
            new_user.id,
            _mask_email(request.email),
            _mask_phone(request.phone),
        )
        return {
            "message": "注册成功",
            "username": new_user.username,
            "user_id": new_user.id,
        }
    except HTTPException:
        raise
    except Exception:
        # Avoid logging password/email_code; only identifiers.
        logger.exception(
            "Register failed (unexpected) username=%s email=%s phone=%s",
            request.username,
            _mask_email(request.email),
            _mask_phone(request.phone),
        )
        raise


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录接口。

    Args:
        form_data: OAuth2 表单数据
        db: 数据库会话

    Returns:
        包含 access_token 的响应

    Raises:
        HTTPException: 用户名或密码错误
    """
    # 查询用户（兼容：username / email / phone）
    identifier = form_data.username
    if _looks_like_phone(identifier):
        user = (
            await db.execute(select(User).where(User.phone == identifier))
        ).scalar_one_or_none()
        if user is None:
            user = (
                await db.execute(select(User).where(User.username == identifier))
            ).scalar_one_or_none()
    elif _looks_like_email(identifier):
        user = (
            await db.execute(select(User).where(User.email == identifier))
        ).scalar_one_or_none()
        if user is None:
            user = (
                await db.execute(select(User).where(User.username == identifier))
            ).scalar_one_or_none()
    else:
        user = (
            await db.execute(select(User).where(User.username == identifier))
        ).scalar_one_or_none()
        if user is None:
            user = (
                await db.execute(select(User).where(User.email == identifier))
            ).scalar_one_or_none()
        if user is None:
            user = (
                await db.execute(select(User).where(User.phone == identifier))
            ).scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "user_id": user.id
    }

