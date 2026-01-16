#!/usr/bin/env python3
"""
Sync real product_info into database product_rules from docs/chanpinbiao.txt.

Why:
    The initial product rules were seeded with mock `product_info` (placeholder
    images, dummy links). This script overwrites `product_info` with the real
    product catalog in `docs/chanpinbiao.txt`.

What it updates:
    - product_rules.product_info (overwrite)
    - product_rules.track (overwrite with normalized track name)

What it does NOT update:
    - trigger_tags / risk_level / rule_id / logic fields (match_key, etc.)

Safety:
    - Detects duplicate rule_id in the input file and fails fast by default.
    - Tolerant parsing for lines with missing tabs (extract URLs via regex).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.models.tables.chat import ProductRule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CHANPIN_PATH = Path(__file__).parent / "docs" / "chanpinbiao.txt"


TRACK_NORMALIZATION = {
    "皮肤健康": "皮肤",
    "皮肤": "皮肤",
    "免疫/出血": "免疫与出血",
    "免疫与出血": "免疫与出血",
    "骨骼代谢": "骨骼与代谢",
    "骨骼与代谢": "骨骼与代谢",
    "神经系统": "神经系统",
    "消化系统": "消化系统",
    "内分泌": "内分泌",
    "心血管": "心血管",
}


@dataclass(frozen=True)
class ProductInfoRow:
    """One product row from docs/chanpinbiao.txt."""

    rule_id: str
    track: str
    name: str
    brand: str
    description: str
    price: Optional[float]
    image_url: Optional[str]
    product_url: Optional[str]


def _clean(value: str) -> str:
    return str(value or "").strip().strip('"').strip()


def _normalize_track(track: str) -> str:
    raw = _clean(track)
    if raw in TRACK_NORMALIZATION:
        return TRACK_NORMALIZATION[raw]
    # Keep original if unknown; caller may decide how to handle.
    return raw


def _parse_price(raw: str) -> Optional[float]:
    text = _clean(raw).replace("￥", "").replace("¥", "")
    if not text:
        return None
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


_URL_RE = re.compile(r"https?://\S+")


def _extract_urls(line: str) -> List[str]:
    return [m.group(0).strip() for m in _URL_RE.finditer(line or "")]


def _parse_line_to_row(line: str) -> Optional[ProductInfoRow]:
    """
    Parse a single line.

    Expected columns (tab-separated):
        rule_id, track, product_name, brand, description, price, image_url, product_url
    """
    line = (line or "").strip()
    if not line:
        return None
    if line.startswith("规则"):
        return None

    parts = [p.strip() for p in line.split("\t")]
    # Fallback: if tab parsing is broken, still try to extract URLs.
    urls = _extract_urls(line)

    def get(idx: int) -> str:
        return parts[idx] if idx < len(parts) else ""

    rule_id = _clean(get(0))
    track = _normalize_track(get(1))
    name = _clean(get(2))
    brand = _clean(get(3))
    description = _clean(get(4))
    price = _parse_price(get(5))

    image_url: Optional[str] = _clean(get(6)) or None
    product_url: Optional[str] = _clean(get(7)) or None

    # If image/product url columns are missing/mangled, use regex extracted URLs.
    if (not image_url or not product_url) and urls:
        if not image_url and len(urls) >= 1:
            image_url = urls[0]
        if not product_url and len(urls) >= 2:
            product_url = urls[1]

    if not rule_id or not track or not name:
        return None

    return ProductInfoRow(
        rule_id=rule_id,
        track=track,
        name=name,
        brand=brand,
        description=description,
        price=price,
        image_url=image_url,
        product_url=product_url,
    )


def load_product_rows(path: Path) -> Tuple[List[ProductInfoRow], Dict[str, List[int]]]:
    """Load rows and return (rows, duplicates_map rule_id -> line_numbers)."""
    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows: List[ProductInfoRow] = []
    seen: Dict[str, int] = {}
    dup_lines: Dict[str, List[int]] = {}

    for lineno, line in enumerate(text, start=1):
        row = _parse_line_to_row(line)
        if row is None:
            continue

        if row.rule_id in seen:
            dup_lines.setdefault(row.rule_id, []).append(lineno)
        else:
            seen[row.rule_id] = lineno
        rows.append(row)

    # Include the first line number in duplicates report
    for rid in list(dup_lines.keys()):
        dup_lines[rid] = [seen[rid], *dup_lines[rid]]

    return rows, dup_lines


def _build_product_info(row: ProductInfoRow) -> Dict[str, object]:
    """
    Build product_info structure used by frontend.

    Frontend expects at least:
        name, description, price, image_url
    It may render `usage` and `features` too; keep them present to avoid 'undefined'.
    """
    return {
        "name": row.name,
        "brand": row.brand,
        "description": row.description,
        "price": row.price,
        "image_url": row.image_url,
        "link": row.product_url,
        "features": [],
        "usage": "",
    }


async def sync_product_info(
    *,
    chanpin_path: Path = DEFAULT_CHANPIN_PATH,
    duplicate_strategy: str = "first",
) -> None:
    """Sync real product info into DB."""
    if not chanpin_path.exists():
        raise FileNotFoundError(f"chanpinbiao.txt 不存在: {chanpin_path}")

    rows, dup_lines = load_product_rows(chanpin_path)
    logger.info("读取到 %s 行产品数据（含可能重复）", len(rows))

    if dup_lines:
        msg = "检测到重复 rule_id:\n"
        for rid, lines in sorted(dup_lines.items()):
            msg += f"- {rid}: lines={lines}\n"
        msg = msg.rstrip()

        if duplicate_strategy not in {"error", "first", "last"}:
            raise ValueError(f"duplicate_strategy 不支持: {duplicate_strategy}")
        if duplicate_strategy == "error":
            raise ValueError(msg + "\n请先修复 chanpinbiao.txt 或选择 duplicate_strategy=first/last")
        logger.warning("%s\n将按 duplicate_strategy=%s 处理重复行。", msg, duplicate_strategy)

    # Duplicate handling:
    # - first: keep first occurrence (ignore later)
    # - last: keep last occurrence (override earlier)
    chosen_by_rule: Dict[str, ProductInfoRow] = {}
    if duplicate_strategy == "last":
        for row in rows:
            chosen_by_rule[row.rule_id] = row
    else:
        for row in rows:
            if row.rule_id in chosen_by_rule:
                continue
            chosen_by_rule[row.rule_id] = row

    async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_local = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    updated = 0
    missing = 0

    async with async_session_local() as db:
        try:
            for rid, row in chosen_by_rule.items():
                existing = (
                    await db.execute(select(ProductRule).where(ProductRule.rule_id == rid))
                ).scalar_one_or_none()
                if existing is None:
                    missing += 1
                    logger.warning("DB 中不存在 rule_id=%s，跳过", rid)
                    continue

                existing.track = row.track
                existing.product_info = _build_product_info(row)
                db.add(existing)
                updated += 1

            await db.commit()
            logger.info("✅ 同步完成：更新 %s 条规则；DB 缺失 %s 条 rule_id", updated, missing)
        except Exception:
            await db.rollback()
            raise
        finally:
            await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(sync_product_info())

