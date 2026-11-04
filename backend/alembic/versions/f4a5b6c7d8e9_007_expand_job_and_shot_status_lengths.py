"""007_expand_job_and_shot_status_lengths

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-11-04 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Expand jobs.status to VARCHAR(32) to accommodate CANCEL_REQUESTED and CANCELLED
    op.alter_column(
        'jobs',
        'status',
        type_=sa.String(length=32),
        existing_type=sa.String(length=7),
        existing_nullable=False,
    )

    # Expand shots.status to VARCHAR(32) to accommodate CANCEL_REQUESTED and CANCELLED
    op.alter_column(
        'shots',
        'status',
        type_=sa.String(length=32),
        existing_type=sa.String(length=10),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'shots',
        'status',
        type_=sa.String(length=10),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        'jobs',
        'status',
        type_=sa.String(length=7),
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
