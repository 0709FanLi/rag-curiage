"""Report parse service.

Parse attached image/PDF report files into OCR text and persist it to session.
This is invoked during report generation (not during upload).
"""

from __future__ import annotations

import io
import logging
from typing import List, Tuple
from urllib.parse import urlparse

import httpx
import pypdfium2 as pdfium
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models.tables import Session as DBSession
from src.services.oss_service import OSSService
from src.services.qwen_vl_service import qwen_vl_service
from src.services.session_attachment_service import (
    OCR_SOURCE_URLS_KEY,
    get_attached_file_urls,
)

logger = logging.getLogger(__name__)


def _is_pdf(url: str) -> bool:
    """Heuristic to determine if a URL points to a PDF file."""
    try:
        path = urlparse(url).path.lower()
    except Exception:
        path = (url or "").lower()
    return path.endswith(".pdf")


def _pdf_to_images(pdf_bytes: bytes, scale: float = 2.0) -> List[bytes]:
    """Convert a PDF bytes blob to a list of PNG images (one per page)."""
    images: List[bytes] = []
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    for page_idx in range(len(pdf_doc)):
        page = pdf_doc[page_idx]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        img_buffer = io.BytesIO()
        pil_image.save(img_buffer, format="PNG")
        images.append(img_buffer.getvalue())
    return images


async def _extract_ocr_text_from_urls(file_urls: List[str]) -> str:
    """Extract merged OCR text from image/PDF URLs."""
    pdf_urls = [u for u in file_urls if _is_pdf(u)]
    image_urls = [u for u in file_urls if not _is_pdf(u)]

    if len(image_urls) > settings.MAX_OCR_IMAGES:
        raise ValueError(f"单次最多支持解析 {settings.MAX_OCR_IMAGES} 张图片，请分批生成报告")

    merged_parts: List[str] = []

    if image_urls:
        logger.info("OCR: parsing images count=%s", len(image_urls))
        img_text = await qwen_vl_service.parse_multiple_images(image_urls)
        if img_text:
            merged_parts.append(f"【图片OCR解析】\n{img_text}".strip())

    if pdf_urls:
        logger.info("OCR: parsing pdfs (convert-to-images) count=%s", len(pdf_urls))
        pdf_total_bytes = 0
        max_bytes = int(settings.MAX_PDF_TOTAL_MB_PER_BATCH) * 1024 * 1024
        oss_service = OSSService()

        async with httpx.AsyncClient(timeout=settings.GEMINI_TIMEOUT or 300) as client:
            for idx, pdf_url in enumerate(pdf_urls, start=1):
                resp = await client.get(pdf_url)
                resp.raise_for_status()
                pdf_bytes = resp.content
                pdf_total_bytes += len(pdf_bytes)
                if pdf_total_bytes > max_bytes:
                    raise ValueError(
                        f"本次PDF总大小超过限制：<= {settings.MAX_PDF_TOTAL_MB_PER_BATCH}MB，请分批生成报告"
                    )

                try:
                    reader = PdfReader(io.BytesIO(pdf_bytes))
                    num_pages = len(reader.pages)
                except Exception as exc:  # noqa: BLE001
                    raise ValueError("PDF解析失败：无法读取页数，请确认PDF未加密且格式正确") from exc

                if num_pages > settings.MAX_PDF_PAGES:
                    raise ValueError(
                        f"单个PDF页数超过限制：<= {settings.MAX_PDF_PAGES}页，请拆分后生成报告"
                    )

                pdf_images = _pdf_to_images(pdf_bytes)
                image_urls_for_pdf: List[str] = []
                for page_idx, img_bytes in enumerate(pdf_images, start=1):
                    filename = f"pdf_page_{idx}_{page_idx}.png"
                    upload_result = oss_service.upload_file(
                        file_data=img_bytes,
                        filename=filename,
                        category="pdf_images",
                        content_type="image/png",
                    )
                    image_urls_for_pdf.append(upload_result["url"])

                vl_text = await qwen_vl_service.parse_multiple_images(image_urls_for_pdf)
                extracted = (vl_text or "").strip()
                if extracted:
                    merged_parts.append(
                        f"【PDF解析 {idx}/{len(pdf_urls)} | pages={num_pages}】\n{extracted}".strip()
                    )

    return "\n\n".join([p for p in merged_parts if p]).strip()


async def ensure_session_ocr_text(db: AsyncSession, session_id: int) -> None:
    """Ensure a session has OCR text for attached files.

    This will parse attached files only if:
    - there are attached URLs
    - and either `session.ocr_text` is empty OR attachments changed since last parse
    """
    result = await db.execute(select(DBSession).where(DBSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        return

    urls = get_attached_file_urls(session)
    if not urls:
        return

    meta = session.meta_data or {}
    prev_urls = meta.get(OCR_SOURCE_URLS_KEY, [])
    if isinstance(prev_urls, list) and prev_urls == urls and (session.ocr_text or "").strip():
        return

    logger.info("Ensuring OCR text for session=%s urls=%s", session_id, len(urls))
    ocr_text = await _extract_ocr_text_from_urls(urls)
    if not ocr_text:
        # Keep it empty; report generation will still proceed with questionnaire only.
        logger.warning("OCR text is empty for session=%s", session_id)

    meta = session.meta_data or {}
    meta[OCR_SOURCE_URLS_KEY] = urls
    session.meta_data = meta
    session.ocr_text = ocr_text or None

    db.add(session)
    await db.commit()


report_parse_service = type(
    "ReportParseService",
    (),
    {"ensure_session_ocr_text": staticmethod(ensure_session_ocr_text)},
)()




