"""merge_heads

Revision ID: e5aff986e038
Revises: 7f4c2d1a9b8e, a3f4b2c1d6e7, add_prompt_templates, readd_memory_metadata
Create Date: 2026-05-28 15:26:45.006055

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5aff986e038'
down_revision: Union[str, Sequence[str], None] = ('7f4c2d1a9b8e', 'a3f4b2c1d6e7', 'add_prompt_templates', 'readd_memory_metadata')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
