"""Relax legacy lore columns after spine aliases

Revision ID: 005
Revises: 004
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sources' AND column_name = 'path'
          ) THEN
            ALTER TABLE lore_sources ALTER COLUMN path DROP NOT NULL;
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sources' AND column_name = 'content_hash'
          ) THEN
            ALTER TABLE lore_sources ALTER COLUMN content_hash DROP NOT NULL;
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_assets' AND column_name = 'canonical_key'
          ) THEN
            ALTER TABLE lore_assets ALTER COLUMN canonical_key DROP NOT NULL;
          END IF;
        END $$;
        """
    )


def downgrade():
    pass
