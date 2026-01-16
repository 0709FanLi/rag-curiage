"""add users.email/phone and email_verification_codes

Revision ID: 20251229_0002
Revises: 20251229_0001
Create Date: 2025-12-29
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20251229_0002'
down_revision: Union[str, None] = '20251229_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_has_table(conn: sa.engine.Connection, table_name: str) -> bool:
    row = conn.execute(
        sa.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:name LIMIT 1"
        ),
        {"name": table_name},
    ).fetchone()
    return row is not None


def _sqlite_has_column(conn: sa.engine.Connection, table: str, col: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == col for r in rows)


def _sqlite_has_index(conn: sa.engine.Connection, index_name: str) -> bool:
    row = conn.execute(
        sa.text(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=:name LIMIT 1"
        ),
        {"name": index_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    """Upgrade existing DBs (idempotent for sqlite)."""
    conn = op.get_bind()
    dialect = conn.dialect.name

    # 1) users.email / users.phone
    if dialect == "sqlite":
        if _sqlite_has_table(conn, "users"):
            if not _sqlite_has_column(conn, "users", "email"):
                op.add_column("users", sa.Column("email", sa.String(), nullable=True))
            if not _sqlite_has_column(conn, "users", "phone"):
                op.add_column("users", sa.Column("phone", sa.String(), nullable=True))

            if not _sqlite_has_index(conn, "ix_users_email"):
                op.create_index("ix_users_email", "users", ["email"])
            if not _sqlite_has_index(conn, "ix_users_phone"):
                op.create_index("ix_users_phone", "users", ["phone"])
            # Unique index (SQLite allows multiple NULL)
            if not _sqlite_has_index(conn, "ux_users_email"):
                op.create_index("ux_users_email", "users", ["email"], unique=True)
            if not _sqlite_has_index(conn, "ux_users_phone"):
                op.create_index("ux_users_phone", "users", ["phone"], unique=True)

    # 2) email_verification_codes table
    if dialect == "sqlite":
        if not _sqlite_has_table(conn, "email_verification_codes"):
            op.create_table(
                "email_verification_codes",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("email", sa.String(), nullable=False),
                sa.Column("purpose", sa.String(), nullable=False),
                sa.Column("code_hash", sa.String(), nullable=False),
                sa.Column("expires_at", sa.DateTime(), nullable=False),
                sa.Column("used_at", sa.DateTime(), nullable=True),
                sa.Column("send_ip", sa.String(), nullable=True),
                sa.Column("created_at", sa.DateTime(), nullable=False),
            )
            op.create_index(
                "ix_email_verification_codes_id",
                "email_verification_codes",
                ["id"],
            )
            op.create_index(
                "ix_email_verification_codes_email",
                "email_verification_codes",
                ["email"],
            )
            op.create_index(
                "ix_email_verification_codes_purpose",
                "email_verification_codes",
                ["purpose"],
            )


def downgrade() -> None:
    """Downgrade.

SQLite 不支持 DROP COLUMN，这里仅尝试删除 email_verification_codes 表与索引。
"""
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        if _sqlite_has_table(conn, "email_verification_codes"):
            op.drop_index(
                "ix_email_verification_codes_purpose", table_name="email_verification_codes"
            )
            op.drop_index(
                "ix_email_verification_codes_email", table_name="email_verification_codes"
            )
            op.drop_index(
                "ix_email_verification_codes_id", table_name="email_verification_codes"
            )
            op.drop_table("email_verification_codes")


