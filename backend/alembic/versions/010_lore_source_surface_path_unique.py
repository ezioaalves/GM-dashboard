"""Add lore source surface/path uniqueness

Revision ID: 010
Revises: 009
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "010"
down_revision = "009"
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
            UPDATE lore_sources
            SET source_path = path
            WHERE source_path = ''
              AND path IS NOT NULL
              AND path <> '';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sources' AND column_name = 'content_hash'
          ) THEN
            UPDATE lore_sources
            SET source_hash = content_hash
            WHERE source_hash = ''
              AND content_hash IS NOT NULL
              AND content_hash <> '';
          END IF;
        END $$;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_sources_surface_path
          ON lore_sources(source_surface, source_path);
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_lore_sources_surface_path;")
