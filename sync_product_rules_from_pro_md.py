#!/usr/bin/env python3
"""
将 docs/pro.md（来源：pro-table）中的“产品逻辑数据”同步到数据库 product_rules 表。

特点：
- 幂等：按 rule_id upsert（存在则更新，不存在则新增）
- 默认不覆盖已存在的 product_info（避免影响现有前端展示），仅补齐/更新逻辑字段
- 兼容 docs/pro.md 的“表头断行”问题：只解析以 'R-' 开头的数据行
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.models.tables.chat import ProductRule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PRO_MD_PATH = Path(__file__).parent / 'docs' / 'pro.md'


@dataclass(frozen=True)
class ProRuleRow:
    """来自 pro.md 的单行规则数据。"""

    rule_id: str
    track: str
    risk_level: str
    trigger_tags: List[str]
    match_key: Optional[str]
    toc_search_query: Optional[str]
    core_ingredient_name: Optional[str]
    ai_talk_script: Optional[str]
    buying_tip: Optional[str]


def _clean_cell(value: str) -> str:
    return value.strip().strip('"').strip()


def _parse_trigger_tags(raw: str) -> List[str]:
    raw = _clean_cell(raw)
    if not raw or raw in {'(Empty/Default)', 'Empty/Default'}:
        return []

    # 兜底行通常形如 "(无特定标签，兜底推荐)"，也视为无触发标签
    if '兜底' in raw and '无特定' in raw:
        return []

    separators = [',', '，', '、', '。', ';', '；']
    for sep in separators[1:]:
        raw = raw.replace(sep, separators[0])

    tags = []
    for item in raw.split(','):
        tag = item.strip()
        if not tag:
            continue
        tags.append(tag)
    return tags


def load_rules_from_pro_md(pro_md_path: Path) -> List[ProRuleRow]:
    """
    解析 docs/pro.md。

    pro.md 的表头可能有断行和引号，因此我们采用“只解析以 R- 开头的数据行”的策略。
    """
    text = pro_md_path.read_text(encoding='utf-8')
    rows: List[ProRuleRow] = []

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('R-'):
            continue

        parts = line.split('\t')
        if len(parts) < 9:
            logger.warning('跳过列数不足的行(%s列): %s', len(parts), line)
            continue

        rule_id = _clean_cell(parts[0])
        track = _clean_cell(parts[1])
        risk_level = _clean_cell(parts[2])
        trigger_tags = _parse_trigger_tags(parts[3])
        match_key = _clean_cell(parts[4]) or None
        toc_search_query = _clean_cell(parts[5]) or None
        core_ingredient_name = _clean_cell(parts[6]) or None
        ai_talk_script = _clean_cell(parts[7]) or None
        buying_tip = _clean_cell(parts[8]) or None

        rows.append(
            ProRuleRow(
                rule_id=rule_id,
                track=track,
                risk_level=risk_level,
                trigger_tags=trigger_tags,
                match_key=match_key,
                toc_search_query=toc_search_query,
                core_ingredient_name=core_ingredient_name,
                ai_talk_script=ai_talk_script,
                buying_tip=buying_tip,
            )
        )

    return rows


async def sync_product_rules(pro_md_path: Path = DEFAULT_PRO_MD_PATH) -> None:
    """将 pro.md 同步到数据库。"""
    logger.info('📥 读取 pro 表数据: %s', pro_md_path)
    if not pro_md_path.exists():
        raise FileNotFoundError(f'pro.md 不存在: {pro_md_path}')

    rows = load_rules_from_pro_md(pro_md_path)
    logger.info('解析到 %s 条规则', len(rows))

    async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_local = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    created = 0
    updated = 0

    async with async_session_local() as db:
        try:
            for row in rows:
                result = await db.execute(
                    select(ProductRule).where(ProductRule.rule_id == row.rule_id)
                )
                existing = result.scalar_one_or_none()

                if existing is None:
                    rule = ProductRule(
                        rule_id=row.rule_id,
                        track=row.track,
                        risk_level=row.risk_level,
                        trigger_tags=row.trigger_tags,
                        match_key=row.match_key,
                        toc_search_query=row.toc_search_query,
                        core_ingredient_name=row.core_ingredient_name,
                        ai_talk_script=row.ai_talk_script,
                        buying_tip=row.buying_tip,
                        # 不强制填 product_info，避免误导；如业务需要可后续映射补齐
                        product_info=None,
                    )
                    db.add(rule)
                    created += 1
                    continue

                # 更新逻辑字段（保留已有 product_info）
                existing.track = row.track
                existing.risk_level = row.risk_level
                existing.trigger_tags = row.trigger_tags
                existing.match_key = row.match_key
                existing.toc_search_query = row.toc_search_query
                existing.core_ingredient_name = row.core_ingredient_name
                existing.ai_talk_script = row.ai_talk_script
                existing.buying_tip = row.buying_tip
                updated += 1

            await db.commit()
            logger.info('✅ 同步完成：新增 %s，更新 %s', created, updated)
        except Exception as exc:
            await db.rollback()
            logger.error('❌ 同步失败: %s', exc)
            raise
        finally:
            await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(sync_product_rules())


