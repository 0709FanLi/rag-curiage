"""baseline schema

Revision ID: 20251229_0001
Revises: 
Create Date: 2025-12-29
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20251229_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for a fresh database."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    op.create_table(
        'user_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('channel_source', sa.String(), nullable=True),
        sa.Column('channel_ext_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_user_profiles_id', 'user_profiles', ['id'])
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'], unique=True)

    op.create_table(
        'channel_source_options',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('icon_key', sa.String(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('uploaded_file_url', sa.String(), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_sessions_id', 'sessions', ['id'])

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
    )
    op.create_index('ix_messages_id', 'messages', ['id'])

    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=True),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('baichuan_suggestions', sa.Text(), nullable=True),
        sa.Column('recommended_products', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.UniqueConstraint('session_id'),
    )
    op.create_index('ix_reports_id', 'reports', ['id'])

    op.create_table(
        'knowledge_files',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('object_key', sa.String(), nullable=False),
        sa.Column('oss_url', sa.String(), nullable=True),
        sa.Column('kb_type', sa.String(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error_msg', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_knowledge_files_id', 'knowledge_files', ['id'])

    # Optional tables used by product recommendations / sales scripts
    op.create_table(
        'product_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rule_id', sa.String(), nullable=True),
        sa.Column('track', sa.String(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=True),
        sa.Column('trigger_tags', sa.JSON(), nullable=True),
        sa.Column('match_key', sa.String(), nullable=True),
        sa.Column('toc_search_query', sa.Text(), nullable=True),
        sa.Column('core_ingredient_name', sa.String(), nullable=True),
        sa.Column('ai_talk_script', sa.Text(), nullable=True),
        sa.Column('buying_tip', sa.Text(), nullable=True),
        sa.Column('product_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_product_rules_id', 'product_rules', ['id'])
    op.create_index('ix_product_rules_rule_id', 'product_rules', ['rule_id'], unique=True)
    op.create_index('ix_product_rules_track', 'product_rules', ['track'])
    op.create_index('ix_product_rules_match_key', 'product_rules', ['match_key'])

    op.create_table(
        'sales_scripts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('report_id', sa.Integer(), nullable=True),
        sa.Column('tone', sa.String(), nullable=True),
        sa.Column('channel', sa.String(), nullable=True),
        sa.Column('channel_source', sa.String(), nullable=True),
        sa.Column('core_ingredient_name', sa.Text(), nullable=True),
        sa.Column('search_keyword', sa.Text(), nullable=True),
        sa.Column('step1_text', sa.Text(), nullable=False),
        sa.Column('step2_text', sa.Text(), nullable=False),
        sa.Column('step3_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id']),
        sa.UniqueConstraint('report_id', name='uq_sales_script_report_id'),
    )
    op.create_index('ix_sales_scripts_id', 'sales_scripts', ['id'])
    op.create_index('ix_sales_scripts_session_id', 'sales_scripts', ['session_id'])
    op.create_index('ix_sales_scripts_report_id', 'sales_scripts', ['report_id'], unique=True)
    op.create_index('ix_sales_scripts_tone', 'sales_scripts', ['tone'])
    op.create_index('ix_sales_scripts_channel', 'sales_scripts', ['channel'])


def downgrade() -> None:
    """Drop all tables (dangerous)."""
    op.drop_index('ix_sales_scripts_channel', table_name='sales_scripts')
    op.drop_index('ix_sales_scripts_tone', table_name='sales_scripts')
    op.drop_index('ix_sales_scripts_report_id', table_name='sales_scripts')
    op.drop_index('ix_sales_scripts_session_id', table_name='sales_scripts')
    op.drop_index('ix_sales_scripts_id', table_name='sales_scripts')
    op.drop_table('sales_scripts')

    op.drop_index('ix_product_rules_match_key', table_name='product_rules')
    op.drop_index('ix_product_rules_track', table_name='product_rules')
    op.drop_index('ix_product_rules_rule_id', table_name='product_rules')
    op.drop_index('ix_product_rules_id', table_name='product_rules')
    op.drop_table('product_rules')

    op.drop_index('ix_knowledge_files_id', table_name='knowledge_files')
    op.drop_table('knowledge_files')

    op.drop_index('ix_reports_id', table_name='reports')
    op.drop_table('reports')

    op.drop_index('ix_messages_id', table_name='messages')
    op.drop_table('messages')

    op.drop_index('ix_sessions_id', table_name='sessions')
    op.drop_table('sessions')

    op.drop_table('channel_source_options')

    op.drop_index('ix_user_profiles_user_id', table_name='user_profiles')
    op.drop_index('ix_user_profiles_id', table_name='user_profiles')
    op.drop_table('user_profiles')

    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_id', table_name='users')
    op.drop_table('users')


