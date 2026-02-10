"""Re-add value_hash column to memories

Revision ID: readd_value_hash
Revises: add_conversation_context
Create Date: 2026-02-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'readd_value_hash'
down_revision = 'add_conversation_context'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('memories', sa.Column('value_hash', sa.String(length=64), nullable=True))
    try:
        op.create_index(op.f('ix_memories_value_hash'), 'memories', ['value_hash'], unique=False)
    except Exception:
        # index creation is best-effort for different DBs
        pass


def downgrade():
    try:
        op.drop_index(op.f('ix_memories_value_hash'), table_name='memories')
    except Exception:
        pass
    op.drop_column('memories', 'value_hash')
