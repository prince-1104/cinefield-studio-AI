"""002_configurable_duration_and_progress

Revision ID: a7e8b910c234
Revises: 36275ea4dd79
Create Date: 2026-10-28 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7e8b910c234'
down_revision: Union[str, None] = '36275ea4dd79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to projects table
    op.add_column('projects', sa.Column('target_duration', sa.Integer(), server_default='15', nullable=False))
    op.add_column('projects', sa.Column('shot_count', sa.Integer(), server_default='3', nullable=False))
    op.add_column('projects', sa.Column('aspect_ratio', sa.String(length=16), server_default='16:9', nullable=False))
    op.add_column('projects', sa.Column('progress_percent', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('projects', sa.Column('current_stage_label', sa.String(length=128), nullable=True))
    op.add_column('projects', sa.Column('video_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Add columns to shots table
    op.add_column('shots', sa.Column('start_time', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('shots', sa.Column('end_time', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('shots', sa.Column('target_duration', sa.Float(), server_default='5.0', nullable=False))
    op.add_column('shots', sa.Column('actual_duration', sa.Float(), nullable=True))
    op.add_column('shots', sa.Column('camera_motion', sa.String(length=128), nullable=True))
    op.add_column('shots', sa.Column('transition', sa.String(length=128), nullable=True))
    op.add_column('shots', sa.Column('provider_job_id', sa.String(length=255), nullable=True))
    op.add_column('shots', sa.Column('provider_status', sa.String(length=64), nullable=True))


def downgrade() -> None:
    # Remove columns from shots table
    op.drop_column('shots', 'provider_status')
    op.drop_column('shots', 'provider_job_id')
    op.drop_column('shots', 'transition')
    op.drop_column('shots', 'camera_motion')
    op.drop_column('shots', 'actual_duration')
    op.drop_column('shots', 'target_duration')
    op.drop_column('shots', 'end_time')
    op.drop_column('shots', 'start_time')

    # Remove columns from projects table
    op.drop_column('projects', 'video_metadata')
    op.drop_column('projects', 'current_stage_label')
    op.drop_column('projects', 'progress_percent')
    op.drop_column('projects', 'aspect_ratio')
    op.drop_column('projects', 'shot_count')
    op.drop_column('projects', 'target_duration')

