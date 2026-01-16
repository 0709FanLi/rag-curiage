"""销售助手（AI 推荐话术）相关 Schema。"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ToneId = Literal['expert', 'friend']


class ToneOption(BaseModel):
    """话术语气选项。"""

    id: ToneId
    label: str
    is_default: bool = False


class SalesScriptConfigResponse(BaseModel):
    """配置面板需要的静态配置数据。"""

    tones: List[ToneOption]


class SalesScriptGenerateRequest(BaseModel):
    """生成话术请求参数。"""

    tone: ToneId = Field(default='expert')
    channel: Optional[str] = Field(default='wechat_private')
    # 允许为空：前端未选择渠道来源时不应写入默认值
    channel_source: Optional[str] = Field(default=None)
    recommendation_rule_id: Optional[str] = Field(default=None)


class SalesScriptSaveRequest(BaseModel):
    """保存（编辑后）话术请求。"""

    tone: ToneId = Field(default='expert')
    channel: Optional[str] = Field(default='wechat_private')
    # 允许为空：前端未选择渠道来源时不应写入默认值
    channel_source: Optional[str] = Field(default=None)

    # 编辑后的话术内容
    step1_text: str
    step2_text: str
    step3_text: str

    # 编辑后的搜索词/高亮变量（允许覆盖规则表默认值）
    search_keyword: str
    core_ingredient_name: Optional[str] = None


class HighlightSpan(BaseModel):
    """前端高亮片段（基于 substring 定位）。"""

    text: str
    start: int
    end: int
    kind: str  # e.g. "salutation" | "score" | "ingredient" | "search_keyword"


class SalesScriptStep(BaseModel):
    """单个 Step 的话术与高亮信息。"""

    step: Literal['step1', 'step2', 'step3']
    title: str
    text: str
    highlights: List[HighlightSpan] = []


class SalesScriptGenerateResponse(BaseModel):
    """生成话术响应。"""

    session_id: int
    tone: ToneId
    channel: Optional[str] = None
    channel_source: Optional[str] = None
    # 是否为已保存版本（GET 时：已保存=true；未保存则返回一份即时生成并标记 false）
    is_saved: bool = False
    steps: List[SalesScriptStep]
    search_keyword: str
    variables: Dict[str, Any] = {}


