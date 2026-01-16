"""
Qwen-Long file-id 解析服务（DashScope OpenAI 兼容接口）

流程：
1) /files (multipart) 上传 PDF，purpose=file-extract -> file_id
2) /chat/completions 通过 system: fileid://{file_id} 引用文件，提取文本

需要处理“File parsing in progress”场景，做指数退避重试。
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from src.config.settings import settings

logger = logging.getLogger("healthy_rag")


_PARSING_IN_PROGRESS_RE = re.compile(r"file\s+parsing\s+in\s+progress", re.IGNORECASE)


@dataclass
class QwenLongExtractResult:
    file_id: str
    text: str


class QwenLongService:
    def __init__(self) -> None:
        self.api_key = settings.DASHSCOPE_API_KEY
        self.base_url = (settings.QWEN_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        self.model = settings.QWEN_LONG_MODEL or "qwen-long"
        self.timeout = settings.GEMINI_TIMEOUT or 300

    def _headers(self) -> dict:
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置，无法调用 Qwen-Long 文件解析")
        return {"Authorization": f"Bearer {self.api_key}"}

    async def create_file(self, *, file_bytes: bytes, filename: str, purpose: str = "file-extract") -> str:
        """
        上传文件到 DashScope OpenAI 兼容 /files 接口，返回 file_id
        """
        url = f"{self.base_url}/files"

        files = {
            "file": (filename, file_bytes, "application/pdf"),
        }
        data = {"purpose": purpose}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers(), data=data, files=files)
            resp.raise_for_status()
            payload = resp.json()

        file_id = payload.get("id") or payload.get("file_id")
        if not file_id:
            raise ValueError(f"Qwen-Long /files 返回缺少 file_id: {payload}")
        return str(file_id)

    async def extract_text_with_file_id(
        self,
        *,
        file_id: str,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        max_wait_seconds: int = 180,
        initial_backoff: float = 1.0,
        backoff_cap: float = 10.0,
    ) -> str:
        """
        引用 fileid://{file_id} 调用 /chat/completions 抽取文本；如解析未完成则重试。
        """
        url = f"{self.base_url}/chat/completions"

        start = asyncio.get_event_loop().time()
        backoff = initial_backoff

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                try:
                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": f"fileid://{file_id}"},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    }
                    resp = await client.post(url, headers={**self._headers(), "Content-Type": "application/json"}, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return (data["choices"][0]["message"]["content"] or "").strip()
                except httpx.HTTPStatusError as exc:
                    # DashScope 可能在 400/429/500 中返回该提示，这里只对“解析中”做重试
                    body = ""
                    try:
                        body = exc.response.text or ""
                    except Exception:
                        body = ""

                    if not _PARSING_IN_PROGRESS_RE.search(body):
                        raise

                    elapsed = asyncio.get_event_loop().time() - start
                    if elapsed >= max_wait_seconds:
                        raise ValueError(f"Qwen-Long 文件仍在解析中，超过等待上限 {max_wait_seconds}s: {body[:200]}")

                    logger.info("Qwen-Long 文件解析中，等待重试 file_id=%s backoff=%.1fs", file_id, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, backoff_cap)

    async def extract_pdf_text(
        self,
        *,
        pdf_bytes: bytes,
        filename: str,
        prompt: Optional[str] = None,
    ) -> QwenLongExtractResult:
        """
        一站式：上传 PDF -> file_id -> 抽取文本
        """
        if prompt is None:
            prompt = (
                "请提取该PDF中的全部文字内容，尽量保持原有层级与表格信息；"
                "重点保留：检查项目、数值、单位、参考范围、异常标记（↑↓H/L/+/-/阳性/阴性）、结论与建议。"
                "只输出提取到的文字，不要添加解释。"
            )

        file_id = await self.create_file(file_bytes=pdf_bytes, filename=filename)
        text = await self.extract_text_with_file_id(file_id=file_id, prompt=prompt)
        return QwenLongExtractResult(file_id=file_id, text=text)


qwen_long_service = QwenLongService()













