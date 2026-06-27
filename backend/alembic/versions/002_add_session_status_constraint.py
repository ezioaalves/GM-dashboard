"""Add session status column with CHECK constraint

Revision ID: 002
Revises: 001
Create Date: 2026-06-27 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # CHECK constraint already defined in baseline schema.sql
    # This migration is a placeholder for future session-related changes
    pass


def downgrade():
    # No operations to downgrade
    pass
