"""风险等级标准化工具。"""

from __future__ import annotations

from typing import Optional


def normalize_risk_level(raw: Optional[str]) -> str:
    """将风险等级归一为：高 / 中 / 低 / 未评估。

    兼容来源：
    - 中文：高风险/中风险/低风险/亚健康预警等
    - 英文：High/Medium/Low 等
    - 其他模型输出：任意描述（尽量映射，否则回退未评估）

    Args:
        raw: 原始风险描述。

    Returns:
        标准化风险等级：高 / 中 / 低 / 未评估
    """
    if raw is None:
        return "未评估"

    value = str(raw).strip()
    if not value:
        return "未评估"

    lower = value.lower()

    # 明确高
    if "高" in value or lower in ("high", "severe") or "high" in lower:
        return "高"

    # 明确中：包含“中”、英文 Medium、或常见“预警/亚健康”等
    if (
        "中" in value
        or lower in ("medium", "moderate")
        or "medium" in lower
        or "moderate" in lower
        or "预警" in value
        or "亚健康" in value
    ):
        return "中"

    # 明确低
    if "低" in value or lower in ("low", "mild") or "low" in lower:
        return "低"

    return "未评估"


