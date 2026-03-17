"""Placeholder migration to restore revision graph for add_memory_embeddings

Revision ID: add_memory_embeddings
Revises: add_conversation_context
Create Date: 2026-02-03 10:00:00.000000

Note: This is a no-op placeholder created to repair the Alembic revision
graph after the original migration file was removed. The original migration
that added embedding columns was intentionally removed from the codebase;
this stub prevents Alembic from failing when resolving revisions.
"""


# revision identifiers, used by Alembic.
revision = "add_memory_embeddings"
down_revision = "add_conversation_context"
branch_labels = None
depends_on = None


def upgrade():
    # no-op placeholder
    pass


def downgrade():
    # no-op placeholder
    pass
