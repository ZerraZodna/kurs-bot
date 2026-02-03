"""Add embedding columns to memories table for semantic search

Revision ID: add_memory_embeddings
Revises: add_conversation_context
Create Date: 2026-02-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_memory_embeddings'
down_revision = 'add_conversation_context'
branch_labels = None
depends_on = None


def upgrade():
    """Add embedding columns to memories table"""
    # Add columns for storing embeddings
    op.add_column(
        'memories',
        sa.Column('embedding', sa.LargeBinary(), nullable=True)
    )
    op.add_column(
        'memories',
        sa.Column('embedding_version', sa.Integer(), nullable=True, server_default='1')
    )
    op.add_column(
        'memories',
        sa.Column('embedding_generated_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    """Remove embedding columns from memories table"""
    op.drop_column('memories', 'embedding_generated_at')
    op.drop_column('memories', 'embedding_version')
    op.drop_column('memories', 'embedding')
