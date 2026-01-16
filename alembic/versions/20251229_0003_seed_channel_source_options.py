"""seed channel_source_options default rows

Revision ID: 20251229_0003
Revises: 20251229_0002
Create Date: 2025-12-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251229_0003"
down_revision = "20251229_0002"
branch_labels = None
depends_on = None


DEFAULT_OPTIONS: list[tuple[str, str, str | None, int]] = [
    ("douyin", "抖音", "douyin", 10),
    ("wechat_official", "公众号", "gongzhonghao", 20),
    ("wechat_video", "视频号", "shipinhao", 30),
    ("wechat_private", "微信私域", "wechat_private", 40),
    ("xiaohongshu", "小红书", "xiaohongshu", 50),
    ("other", "Other（其他/转介绍）", "other", 90),
]


def upgrade() -> None:
    """Insert default channel source options if missing (idempotent)."""
    conn = op.get_bind()

    # 如果表不存在（极端情况），直接跳过，避免迁移失败。
    inspector = sa.inspect(conn)
    if "channel_source_options" not in inspector.get_table_names():
        return

    for option_id, label, icon_key, sort_order in DEFAULT_OPTIONS:
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM channel_source_options WHERE id = :id LIMIT 1"
            ),
            {"id": option_id},
        ).first()
        if exists:
            continue

        conn.execute(
            sa.text(
                """
                INSERT INTO channel_source_options
                (id, label, icon_key, sort_order, is_active)
                VALUES (:id, :label, :icon_key, :sort_order, 1)
                """
            ),
            {
                "id": option_id,
                "label": label,
                "icon_key": icon_key,
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    """Remove seeded default rows only."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "channel_source_options" not in inspector.get_table_names():
        return

    ids = [x[0] for x in DEFAULT_OPTIONS]
    # SQLite 不支持数组参数的 IN 绑定，这里展开占位符。
    placeholders = ", ".join([f":id{i}" for i in range(len(ids))])
    params = {f"id{i}": ids[i] for i in range(len(ids))}
    conn.execute(
        sa.text(
            f"DELETE FROM channel_source_options WHERE id IN ({placeholders})"
        ),
        params,
    )


