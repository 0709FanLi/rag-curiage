from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, func, UniqueConstraint
from sqlalchemy.orm import relationship
from src.models.database import Base

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    # status: 'active', 'completed'
    status = Column(String, default="active")
    # metadata: 存储年龄、性别、主诉、赛道等上下文信息
    meta_data = Column(JSON, default={})
    # 上传的体检报告文件URL（多个用逗号分隔）
    uploaded_file_url = Column(String, nullable=True)
    # OCR解析的原始文本
    ocr_text = Column(Text, nullable=True)
    # OCR提取的标签（JSON数组）
    ocr_tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    report = relationship("Report", back_populates="session", uselist=False)
    user = relationship("User")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    # role: 'user', 'assistant', 'system'
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=func.now())

    session = relationship("Session", back_populates="messages")

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), unique=True)
    score = Column(Integer)
    risk_level = Column(String)
    # 完整报告内容的 JSON 结构
    content = Column(JSON)
    # 百川模型返回的基础健康建议（用于生成最终报告）
    baichuan_suggestions = Column(Text, nullable=True)
    # 推荐的产品列表（JSON数组）
    recommended_products = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())

    session = relationship("Session", back_populates="report")


class ProductRule(Base):
    """产品推荐规则表"""
    __tablename__ = "product_rules"

    id = Column(Integer, primary_key=True, index=True)
    # 规则ID (如 R-NS-01)
    rule_id = Column(String, unique=True, index=True)
    # 赛道名称 (如 "神经系统", "消化系统")
    track = Column(String, index=True)
    # 风险等级 (高/中/低)
    risk_level = Column(String)
    # 触发标签（JSON数组）
    trigger_tags = Column(JSON)
    # 标准匹配键（B端插槽），如 Sleep_Melatonin_Max
    match_key = Column(String, index=True, nullable=True)
    # 通用搜索词（To C 电商 Search Query）
    toc_search_query = Column(Text, nullable=True)
    # 核心成分名
    core_ingredient_name = Column(String, nullable=True)
    # 推荐理由模板（AI Talk Script）
    ai_talk_script = Column(Text, nullable=True)
    # 选购/避坑指引（Buying Tip）
    buying_tip = Column(Text, nullable=True)
    # 产品信息（JSON对象，包含名称、描述、图片等）
    product_info = Column(JSON)
    created_at = Column(DateTime, default=func.now())


class SalesScript(Base):
    """B端销售助手话术（可编辑可保存）。"""

    __tablename__ = "sales_scripts"
    __table_args__ = (
        UniqueConstraint("report_id", name="uq_sales_script_report_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), unique=True, index=True)
    # 语气风格：expert / friend
    tone = Column(String, default="expert", index=True)
    # 渠道（可扩展）：wechat_private 等
    channel = Column(String, default="wechat_private", index=True)
    channel_source = Column(String, nullable=True)

    # 用于高亮/回放的关键变量（允许为空）
    core_ingredient_name = Column(Text, nullable=True)
    search_keyword = Column(Text, nullable=True)

    # 三段式话术内容
    step1_text = Column(Text, nullable=False)
    step2_text = Column(Text, nullable=False)
    step3_text = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

