"""Add lore spine check constraints

Revision ID: 014
Revises: 013
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_source_type_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_source_type_check
              CHECK (source_type IN ('entity', 'thread', 'session', 'scene', 'asset'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_target_type_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_target_type_check
              CHECK (target_type IN ('entity', 'thread', 'session', 'scene', 'asset'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_direction_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_direction_check
              CHECK (direction IN ('directed', 'bidirectional', 'undirected'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_provenance_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_provenance_check
              CHECK (provenance IN ('wikilink', 'mention', 'asset_embed', 'manual', 'foundry_import', 'ai_suggestion', 'system'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_visibility_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_visibility_check
              CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_freshness_state_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_freshness_state_check
              CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_review_status_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_review_status_check
              CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_relationships_resolved_or_unresolved_target_check'
          ) THEN
            ALTER TABLE lore_relationships
              ADD CONSTRAINT lore_relationships_resolved_or_unresolved_target_check
              CHECK (target_id <> '' OR unresolved_target <> '')
              NOT VALID;
          END IF;
        END $$;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE lore_relationships
          DROP CONSTRAINT IF EXISTS lore_relationships_resolved_or_unresolved_target_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_review_status_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_freshness_state_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_visibility_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_provenance_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_direction_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_target_type_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_source_type_check;
        """
    )
