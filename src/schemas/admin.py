from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- 看板相关 ---

class DashboardMetricsResponse(BaseModel):
    consults: int
    reports: int
    converting_reports: int
    total_clicks: int
    conversion_rate: float

class FunnelStep(BaseModel):
    label: str
    value: int
    percentage: int

class DashboardFunnelResponse(BaseModel):
    steps: List[FunnelStep]

class TrackDistributionItem(BaseModel):
    name: str
    value: int
    color: str

class DashboardDistributionResponse(BaseModel):
    distribution: List[TrackDistributionItem]


# --- 记录列表相关 ---

class RecordListItem(BaseModel):
    rid: str  # 格式化的 Session ID, e.g., R-20231124-01
    uid: str  # 格式化的 User ID, e.g., U-1001
    session_id: int
    user_id: int
    track: str
    risk: str
    health_score: Optional[int] = None
    time: str # 格式化后的时间字符串
    report_time: Optional[str] = None  # 报告开始生成时间（中国时区），可为空（未生成报告）
    status: str # "已转化" | "未转化"
    # 渠道来源标记（用户维度，可为空）
    channel_source: Optional[str] = None
    channel_ext_id: Optional[str] = None

class RecordListResponse(BaseModel):
    total: int
    records: List[RecordListItem]


# --- 记录详情相关 ---

class RecordMessageItem(BaseModel):
    """会话中的单条消息（用于回放完整问卷/对话）。"""

    role: str  # user / assistant / system
    content: str
    created_at: datetime


class RecordDetailResponse(BaseModel):
    rid: str
    uid: str
    track: str
    risk: str
    status: str
    qna: str # 拼接后的问答摘要
    messages: Optional[List[RecordMessageItem]] = None  # 完整问卷/对话记录（按时间顺序）
    report_html: str # HTML 报告快照
    created_at: datetime
    # 销售助手/话术生成可能用到的用户画像字段（可为空）
    age: Optional[int] = None
    gender: Optional[str] = None  # "男" | "女" | None
    score: Optional[int] = None
    # 渠道来源标记（用户维度，可为空）
    channel_source: Optional[str] = None
    channel_ext_id: Optional[str] = None

