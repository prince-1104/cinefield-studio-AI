"""006 Add usage_origin column to ai_usage_records and clean up synthetic test records

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-11-04 08:35:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e3f4a5b6c7d8'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add usage_origin column with server default 'production'
    op.add_column(
        'ai_usage_records',
        sa.Column('usage_origin', sa.String(length=32), nullable=False, server_default='production')
    )
    op.create_index('ix_ai_usage_records_origin', 'ai_usage_records', ['usage_origin'])
    op.create_index('ix_ai_usage_origin_created', 'ai_usage_records', ['usage_origin', 'created_at'])

    # 2. Safely clean up confirmed synthetic unit test records from previous test executions
    # These were generated during pytest test runs with mock IDs
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM ai_usage_records
        WHERE provider_request_id LIKE 'msg_test_%'
           OR provider_task_id LIKE 'task_seedance_%'
           OR provider_task_id LIKE 'task_reconcile_%'
           OR provider_task_id LIKE 'task_test_%'
           OR project_id IN (
               SELECT id FROM projects WHERE product_name IN ('Concurrent Test', 'Test Product')
           )
           OR (project_id IS NULL AND shot_id IS NULL AND job_id IS NULL);
    """))


def downgrade() -> None:
    op.drop_index('ix_ai_usage_origin_created', table_name='ai_usage_records')
    op.drop_index('ix_ai_usage_records_origin', table_name='ai_usage_records')
    op.drop_column('ai_usage_records', 'usage_origin')
