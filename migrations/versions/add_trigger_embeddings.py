"""Add trigger_embeddings table for embedding-driven triggers

Revision ID: add_trigger_embeddings
Revises: add_memory_metadata_columns
Create Date: 2026-02-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_trigger_embeddings'
down_revision = 'add_memory_metadata_columns'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'trigger_embeddings' in inspector.get_table_names():
        # Already exists (e.g., DB recreated manually) — skip creation
        return

    try:
        op.create_table(
            'trigger_embeddings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('action_type', sa.String(length=64), nullable=False),
            sa.Column('embedding', sa.LargeBinary(), nullable=False),
            sa.Column('threshold', sa.Float(), nullable=False, server_default='0.75'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    except Exception:
        # If table already exists (e.g., DB recreated manually), skip
        pass


def downgrade():
    op.drop_table('trigger_embeddings')
"""Add trigger_embeddings table

Revision ID: add_trigger_embeddings
Revises: add_memory_embeddings
Create Date: 2026-02-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_trigger_embeddings'
down_revision = 'add_memory_embeddings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trigger_embeddings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('embedding', sa.LargeBinary(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False, server_default='0.75'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade():
    op.drop_table('trigger_embeddings')
