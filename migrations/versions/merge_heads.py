"""Merge multiple heads into a single linear history

Revision ID: merge_heads
Revises: add_job_states, add_memory_metadata_columns
Create Date: 2026-02-06 12:30:00.000000

This is an empty merge migration to unify multiple heads.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads'
down_revision = (
    'add_job_states',
    'add_memory_metadata_columns',
)
branch_labels = None
depends_on = None


def upgrade():
    # Merge-only revision; no schema changes.
    pass


def downgrade():
    pass
