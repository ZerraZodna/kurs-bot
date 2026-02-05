"""Add job_states table

Revision ID: add_job_states
Revises: add_gdpr_verifications
Create Date: 2026-02-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_job_states'
down_revision = 'add_gdpr_verifications'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'job_states',
        sa.Column('key', sa.String(length=64), primary_key=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('job_states')
