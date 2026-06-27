"""Initial schema with sessions table

Revision ID: 001
Revises:
Create Date: 2026-06-27 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # This migration assumes the schema.sql has already been applied
    # or will be applied separately. This is a placeholder for the
    # Alembic migration history.
    pass


def downgrade():
    pass
