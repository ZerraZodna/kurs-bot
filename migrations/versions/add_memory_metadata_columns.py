"""Add missing metadata columns to memories

Revision ID: add_memory_metadata_columns
Revises: add_gdpr_tables
Create Date: 2026-02-04 12:30:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_memory_metadata_columns"
down_revision = "add_gdpr_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("memories", sa.Column("value_hash", sa.String(length=64), nullable=True))
    op.add_column("memories", sa.Column("conflict_group_id", sa.String(length=64), nullable=True))
    op.add_column("memories", sa.Column("source", sa.String(length=64), nullable=True))
    op.add_column("memories", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("memories", "archived_at")
    op.drop_column("memories", "source")
    op.drop_column("memories", "conflict_group_id")
    op.drop_column("memories", "value_hash")
