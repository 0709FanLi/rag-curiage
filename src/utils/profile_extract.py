"""用户画像信息提取工具（年龄/性别等）。"""

from __future__ import annotations

import re
from typing import Optional, Tuple


def extract_age_gender(text: str) -> Tuple[Optional[int], Optional[str]]:
    """从用户自由文本中提取年龄与性别。

    支持典型输入：
    - "33岁 男 鼻塞"
    - "33 男 鼻塞"
    - "女 28 失眠"
    - "年龄33 性别男"

    Args:
        text: 用户输入文本。

    Returns:
        (age, gender)：
        - age: 1~120 的整数，否则为 None
        - gender: "男" / "女" / None
    """
    if not text or not isinstance(text, str):
        return None, None

    cleaned = text.strip()
    if not cleaned:
        return None, None

    gender: Optional[str] = None
    if "女" in cleaned and "男性" not in cleaned:
        gender = "女"
    elif "男" in cleaned and "女性" not in cleaned:
        gender = "男"

    age: Optional[int] = None

    # 1) 显式“岁”
    match = re.search(r"(?<!\d)(\d{1,3})\s*岁", cleaned)
    if match:
        try:
            candidate = int(match.group(1))
            if 1 <= candidate <= 120:
                age = candidate
        except Exception:
            age = None

    # 2) 形如 “33 男 ...” / “33女 ...”
    if age is None:
        match = re.match(r"^\s*(\d{1,3})\s*(?:岁)?\s*(男|女)\b", cleaned)
        if match:
            try:
                candidate = int(match.group(1))
                if 1 <= candidate <= 120:
                    age = candidate
                    gender = match.group(2)
            except Exception:
                age = None

    # 3) 形如 “男 33 ...” / “女28 ...”
    if age is None:
        match = re.match(r"^\s*(男|女)\s*(\d{1,3})\b", cleaned)
        if match:
            try:
                candidate = int(match.group(2))
                if 1 <= candidate <= 120:
                    age = candidate
                    gender = match.group(1)
            except Exception:
                age = None

    # 4) 兜底：抓取 “年龄xx”
    if age is None:
        match = re.search(r"(?:年龄|年齡)\s*[:：]?\s*(\d{1,3})", cleaned)
        if match:
            try:
                candidate = int(match.group(1))
                if 1 <= candidate <= 120:
                    age = candidate
            except Exception:
                age = None

    return age, gender


