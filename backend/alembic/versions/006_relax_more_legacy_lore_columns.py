"""Relax remaining legacy lore import columns

Revision ID: 006
Revises: 005
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sources' AND column_name = 'source_mtime'
          ) THEN
            ALTER TABLE lore_sources ALTER COLUMN source_mtime DROP NOT NULL;
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sections' AND column_name = 'ordinal'
          ) THEN
            ALTER TABLE lore_sections ALTER COLUMN ordinal DROP NOT NULL;
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_relationships' AND column_name = 'source_entity_id'
          ) THEN
            ALTER TABLE lore_relationships ALTER COLUMN source_entity_id DROP NOT NULL;
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_relationships' AND column_name = 'target_slug'
          ) THEN
            ALTER TABLE lore_relationships ALTER COLUMN target_slug DROP NOT NULL;
          END IF;
        END $$;
        """
    )


def downgrade():
    pass
