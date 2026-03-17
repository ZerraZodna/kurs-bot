"""Add GDPR verification table

Revision ID: add_gdpr_verifications
Revises: add_gdpr_tables
Create Date: 2026-02-04 18:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_gdpr_verifications"
down_revision = "add_gdpr_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gdpr_verifications",
        sa.Column("verification_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("request_payload", sa.Text(), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("gdpr_verifications")
