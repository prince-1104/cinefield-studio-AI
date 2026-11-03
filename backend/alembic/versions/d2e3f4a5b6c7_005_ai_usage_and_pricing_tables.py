"""005_ai_usage_and_pricing_tables

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-11-04 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add started_at and completed_at to shots
    op.add_column(
        'shots',
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'shots',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Create ai_model_pricing table
    op.create_table(
        'ai_model_pricing',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('billing_unit', sa.String(length=32), nullable=False, server_default='tokens'),
        sa.Column('input_price_per_million', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('output_price_per_million', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('cached_input_price_per_million', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('video_price_per_second', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('video_price_per_minute', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('effective_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='USD'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(
        'ix_ai_pricing_provider_model',
        'ai_model_pricing',
        ['provider', 'model'],
    )
    op.create_index(
        'ix_ai_pricing_effective',
        'ai_model_pricing',
        ['effective_from', 'effective_until'],
    )

    # 3. Create ai_usage_records table
    op.create_table(
        'ai_usage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('shot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shots.id', ondelete='SET NULL'), nullable=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('pricing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_model_pricing.id', ondelete='SET NULL'), nullable=True),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('operation', sa.String(length=64), nullable=False),
        sa.Column('provider_request_id', sa.String(length=255), nullable=True),
        sa.Column('provider_task_id', sa.String(length=255), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cached_input_tokens', sa.Integer(), nullable=True),
        sa.Column('video_duration_seconds', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('billing_unit', sa.String(length=32), nullable=False, server_default='tokens'),
        sa.Column('unit_quantity', sa.Numeric(precision=14, scale=4), nullable=False, server_default='0'),
        sa.Column('unit_price', sa.Numeric(precision=14, scale=6), nullable=False, server_default='0'),
        sa.Column('estimated_cost', sa.Numeric(precision=14, scale=6), nullable=False, server_default='0'),
        sa.Column('actual_cost', sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='USD'),
        sa.Column('cost_status', sa.String(length=32), nullable=False, server_default='ESTIMATED'),
        sa.Column('request_status', sa.String(length=32), nullable=False, server_default='SUCCESS'),
        sa.Column('error_code', sa.String(length=128), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_ai_usage_records_project_id', 'ai_usage_records', ['project_id'])
    op.create_index('ix_ai_usage_records_shot_id', 'ai_usage_records', ['shot_id'])
    op.create_index('ix_ai_usage_records_job_id', 'ai_usage_records', ['job_id'])
    op.create_index('ix_ai_usage_records_provider', 'ai_usage_records', ['provider'])
    op.create_index('ix_ai_usage_records_model', 'ai_usage_records', ['model'])
    op.create_index('ix_ai_usage_records_operation', 'ai_usage_records', ['operation'])
    op.create_index('ix_ai_usage_records_cost_status', 'ai_usage_records', ['cost_status'])
    op.create_index('ix_ai_usage_records_request_status', 'ai_usage_records', ['request_status'])
    op.create_index('ix_ai_usage_records_created_at', 'ai_usage_records', ['created_at'])
    op.create_index('ix_ai_usage_records_provider_task_id', 'ai_usage_records', ['provider_task_id'])
    op.create_index('ix_ai_usage_proj_created', 'ai_usage_records', ['project_id', 'created_at'])
    op.create_index('ix_ai_usage_prov_model', 'ai_usage_records', ['provider', 'model', 'created_at'])


def downgrade() -> None:
    op.drop_table('ai_usage_records')
    op.drop_table('ai_model_pricing')
    op.drop_column('shots', 'completed_at')
    op.drop_column('shots', 'started_at')

