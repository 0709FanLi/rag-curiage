from sqlalchemy import Column, DateTime, Integer, String, Text, func
from src.models.database import Base


class UserProfile(Base):
    """用户画像（用于运营/销售侧的渠道来源标记等）。"""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)
    # 渠道来源（允许为空：未标记）
    channel_source = Column(String, nullable=True)
    # 外部ID/备注（允许为空）
    channel_ext_id = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=func.now())


class EmailVerificationCode(Base):
    """邮箱验证码表（只存 hash，不存明文）。"""

    __tablename__ = "email_verification_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    purpose = Column(String, index=True, nullable=False, default="register")
    code_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    send_ip = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class ChannelSourceOption(Base):
    """渠道来源配置选项（用于下拉配置，允许后台动态维护）。"""

    __tablename__ = "channel_source_options"

    id = Column(String, primary_key=True)  # 英文标识符，如 douyin / wechat_private
    label = Column(String, nullable=False)  # 展示文案（允许中文）
    icon_key = Column(String, nullable=True)  # 前端图标映射 key
    sort_order = Column(Integer, default=0, nullable=False)  # 排序权重（越小越靠前）
    is_active = Column(Integer, default=1, nullable=False)  # 1启用 / 0禁用（SQLite无Boolean）
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

