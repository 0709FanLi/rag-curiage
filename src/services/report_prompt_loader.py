from __future__ import annotations

from dataclasses import dataclass

from src.services.prompts import (
    BAICHUAN_FULL_REPORT_PROMPT,
    DEEPSEEK_REPORT_PROMPT,
    GEMINI_REPORT_PROMPT,
    REPORT_HTML_TEMPLATE_EX,
)


@dataclass(frozen=True)
class ReportPrompts:
    baichuan: str
    deepseek: str
    gemini: str


def load_report_prompts() -> ReportPrompts:
    """固化版本：从代码常量返回三段提示词（发布时不依赖 update/update.md）。"""
    return ReportPrompts(
        baichuan=BAICHUAN_FULL_REPORT_PROMPT,
        deepseek=DEEPSEEK_REPORT_PROMPT,
        gemini=GEMINI_REPORT_PROMPT,
    )


def load_report_html_template() -> str:
    """固化版本：从代码常量返回固定HTML模板（发布时不依赖 update/ex.html）。"""
    return REPORT_HTML_TEMPLATE_EX


