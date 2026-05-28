"""add_custom_message_to_schedules

Revision ID: b0d9fb1fbd4c
Revises: e5aff986e038
Create Date: 2026-05-28 15:26:52.512252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0d9fb1fbd4c'
down_revision: Union[str, Sequence[str], None] = 'e5aff986e038'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add custom_message column to schedules table."""
    op.add_column("schedules", sa.Column("custom_message", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove custom_message column."""
    op.drop_column("schedules", "custom_message")
