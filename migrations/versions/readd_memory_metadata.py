"""Re-add memory metadata columns to memories

Revision ID: readd_memory_metadata
Revises: readd_value_hash
Create Date: 2026-02-10 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'readd_memory_metadata'
down_revision = 'readd_value_hash'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('memories', sa.Column('conflict_group_id', sa.String(length=64), nullable=True))
    op.add_column('memories', sa.Column('source', sa.String(length=64), nullable=True, server_default='dialogue_engine'))
    op.add_column('memories', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('memories', 'archived_at')
    op.drop_column('memories', 'source')
    op.drop_column('memories', 'conflict_group_id')
