"""add lesson to users

Revision ID: 7f4c2d1a9b8e
Revises: merge_heads
Create Date: 2026-03-10 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f4c2d1a9b8e"
down_revision: str | Sequence[str] | None = "merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("lesson", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "lesson")
