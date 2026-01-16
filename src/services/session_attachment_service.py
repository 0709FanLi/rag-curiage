"""Session attachment service.

This module centralizes how uploaded file URLs are stored on a chat Session.

Design:
- Frontends upload files to `/upload/file` and receive a `file_url`.
- Frontends then call `/chat/upload-report` (renamed semantics) to **attach**
  those URLs to the session (no OCR parsing here).
- Report generation reads attached URLs and performs OCR parsing only when
  generating the report.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Session as DBSession


ATTACHED_FILE_URLS_KEY = "attached_file_urls"
OCR_SOURCE_URLS_KEY = "ocr_source_urls"


def _normalize_urls(urls: List[str]) -> List[str]:
    """Normalize and de-duplicate URLs while preserving order."""
    normalized: List[str] = []
    seen: set[str] = set()
    for raw in urls or []:
        url = str(raw or "").strip()
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized


def get_attached_file_urls(session: DBSession) -> List[str]:
    """Return attached file URLs from session metadata."""
    meta: Dict[str, Any] = session.meta_data or {}
    raw = meta.get(ATTACHED_FILE_URLS_KEY, [])
    if isinstance(raw, str):
        # Backward compatibility: comma separated string
        items = [x.strip() for x in raw.split(",") if x.strip()]
        return _normalize_urls(items)
    if isinstance(raw, list):
        return _normalize_urls([str(x) for x in raw])
    return []


async def set_attached_file_urls(
    db: AsyncSession,
    session: DBSession,
    file_urls: List[str],
) -> List[str]:
    """Persist attached file URLs to a session.

    This method does NOT perform any OCR parsing. It will:
    - store URLs in `session.meta_data[ATTACHED_FILE_URLS_KEY]`
    - store a backward compatible `session.uploaded_file_url` (comma separated)
    - invalidate `session.ocr_text` and `session.ocr_tags` if URLs changed

    Args:
        db: SQLAlchemy async session.
        session: Target DB session row.
        file_urls: URLs to attach.

    Returns:
        The normalized attached URL list.
    """
    urls = _normalize_urls(file_urls)
    before = get_attached_file_urls(session)

    # IMPORTANT:
    # `Session.meta_data` is a plain JSON column. In-place mutations on an
    # existing dict may NOT be detected by SQLAlchemy unless MutableDict is
    # used. Always copy to ensure the ORM marks the column as changed.
    meta: Dict[str, Any] = dict(session.meta_data or {})
    meta[ATTACHED_FILE_URLS_KEY] = urls
    session.meta_data = meta

    session.uploaded_file_url = ",".join(urls) if urls else None

    if urls != before:
        # Invalidate OCR & tags so report generation can re-parse.
        session.ocr_text = None
        session.ocr_tags = None
        meta.pop(OCR_SOURCE_URLS_KEY, None)
        session.meta_data = meta

    db.add(session)
    await db.commit()
    return urls



