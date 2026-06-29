"""Relax legacy relationship confidence

Revision ID: 007
Revises: 006
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE lore_relationships
          ALTER COLUMN confidence DROP NOT NULL,
          ALTER COLUMN confidence DROP DEFAULT;
        """
    )


def downgrade():
    pass
