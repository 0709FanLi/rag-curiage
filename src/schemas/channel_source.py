"""渠道来源（用户画像）相关 Schema。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ChannelSourceOption(BaseModel):
    """渠道来源选项（用于前端配置下拉）。"""

    id: str
    label: str
    icon_key: Optional[str] = None


class ChannelSourceConfigResponse(BaseModel):
    """渠道来源配置接口响应。"""

    options: List[ChannelSourceOption]


class UpdateChannelSourceRequest(BaseModel):
    """更新渠道来源请求。

    说明：后端允许为空，表示“未标记/清空标记”。
    """

    channel_source: Optional[str] = Field(default=None, max_length=50)
    channel_ext_id: Optional[str] = Field(default=None, max_length=500)

    @field_validator("channel_source")
    @classmethod
    def validate_channel_source(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return value

    @field_validator("channel_ext_id")
    @classmethod
    def validate_channel_ext_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class UpdateChannelSourceResponse(BaseModel):
    """更新渠道来源响应（用于列表行/详情页局部刷新）。"""

    user_id: int
    channel_source: Optional[str] = None
    channel_ext_id: Optional[str] = None


