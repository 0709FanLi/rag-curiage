"""Report HTML sanitizer utilities.

生产环境中，模型可能输出“JSON + HTML片段”且 HTML 不一定以 <html>/<DOCTYPE> 开头。
若后端未正确分割，会导致 JSON 被写入 report.content.html 并被前端直接渲染。

本模块提供用于定位 HTML 起点与剥离前置 JSON 的工具函数。
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Tuple


def find_html_start_index(text: str) -> int:
    """在模型输出中定位“HTML正文”开始位置。

    Args:
        text: 模型输出文本

    Returns:
        HTML 起始索引；找不到则返回 -1。
    """
    if not text:
        return -1

    candidates = []
    lowered = text.lower()
    for mark in ("<!doctype html", "<html"):
        idx = lowered.find(mark)
        if idx != -1:
            candidates.append(idx)

    # 兼容：HTML 片段（固定模板核心容器）
    m = re.search(
        r'(?is)<\s*div\b[^>]*class\s*=\s*["\'][^"\']*\breport-container\b[^"\']*["\']',
        text,
    )
    if m:
        candidates.append(m.start())

    return min(candidates) if candidates else -1


def strip_leading_json(raw_html: str) -> Tuple[str, Optional[Any]]:
    """若字符串以 JSON 开头，则剥离 JSON 前缀，返回剩余 HTML。

    Args:
        raw_html: 可能包含 JSON + HTML 的字符串

    Returns:
        (sanitized_html, parsed_json_or_none)
    """
    if not raw_html:
        return "", None

    stripped = raw_html.lstrip()
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return raw_html, None

    try:
        decoder = json.JSONDecoder()
        obj, end = decoder.raw_decode(stripped)
        remainder = stripped[end:].lstrip()
        return remainder, obj
    except Exception:
        return raw_html, None


