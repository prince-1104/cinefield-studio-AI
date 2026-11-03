"""004_video_model_selection

Revision ID: c1a2b3d4e5f6
Revises: b8f9c012d345
Create Date: 2026-11-03 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = 'b8f9c012d345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add video model selection columns to projects table
    op.add_column(
        'projects',
        sa.Column('selected_video_model', sa.String(length=128), nullable=True, server_default='seedance-1-0-pro-250528'),
    )
    op.add_column(
        'projects',
        sa.Column('selected_video_provider', sa.String(length=64), nullable=True, server_default='seedance'),
    )

    # Add provider & model tracking columns to shots table
    op.add_column(
        'shots',
        sa.Column('provider', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'shots',
        sa.Column('model', sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('shots', 'model')
    op.drop_column('shots', 'provider')
    op.drop_column('projects', 'selected_video_provider')
    op.drop_column('projects', 'selected_video_model')

