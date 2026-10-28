"""003_timeline_edits_table

Revision ID: b8f9c012d345
Revises: a7e8b910c234
Create Date: 2026-10-28 23:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b8f9c012d345'
down_revision: Union[str, None] = 'a7e8b910c234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'timeline_edits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('timeline_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('rendered_video_path', sa.Text(), nullable=True),
        sa.Column('render_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_timeline_edits_project_id', 'timeline_edits', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_timeline_edits_project_id', table_name='timeline_edits')
    op.drop_table('timeline_edits')

