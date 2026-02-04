"""Add GDPR consent/audit/request tables and user flags

Revision ID: add_gdpr_tables
Revises: add_memory_embeddings
Create Date: 2026-02-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_gdpr_tables'
down_revision = 'add_memory_embeddings'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('processing_restricted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('restriction_reason', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'consent_logs',
        sa.Column('consent_id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('scope', sa.String(length=64), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.Column('consent_version', sa.String(length=32), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'gdpr_requests',
        sa.Column('request_id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('request_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=64), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'gdpr_audit_logs',
        sa.Column('audit_id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('gdpr_audit_logs')
    op.drop_table('gdpr_requests')
    op.drop_table('consent_logs')
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'is_deleted')
    op.drop_column('users', 'restriction_reason')
    op.drop_column('users', 'processing_restricted')
