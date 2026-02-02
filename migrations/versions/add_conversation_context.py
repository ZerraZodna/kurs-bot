"""Add conversation context columns to MessageLog"""
from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = 'add_conversation_context'
down_revision = '579b16a573a2_add_is_active_to_memory'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to message_logs table
    op.add_column('message_logs', sa.Column('conversation_thread_id', sa.String(64), nullable=True))
    op.add_column('message_logs', sa.Column('message_role', sa.String(16), nullable=False, server_default='user'))


def downgrade() -> None:
    op.drop_column('message_logs', 'message_role')
    op.drop_column('message_logs', 'conversation_thread_id')
