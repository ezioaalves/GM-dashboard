"""Add core spine check constraints

Revision ID: 013
Revises: 012
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE sync_jobs
        SET status = 'queued'
        WHERE status = 'pending';

        ALTER TABLE sync_jobs
          ALTER COLUMN status SET DEFAULT 'queued';

        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'sync_reviews_source_surface_check'
          ) THEN
            ALTER TABLE sync_reviews
              ADD CONSTRAINT sync_reviews_source_surface_check
              CHECK (source_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'sync_reviews_target_surface_check'
          ) THEN
            ALTER TABLE sync_reviews
              ADD CONSTRAINT sync_reviews_target_surface_check
              CHECK (target_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'sync_reviews_review_status_check'
          ) THEN
            ALTER TABLE sync_reviews
              ADD CONSTRAINT sync_reviews_review_status_check
              CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'sync_jobs_status_check'
          ) THEN
            ALTER TABLE sync_jobs
              ADD CONSTRAINT sync_jobs_status_check
              CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'blocked', 'cancelled'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'sync_jobs_source_surface_check'
          ) THEN
            ALTER TABLE sync_jobs
              ADD CONSTRAINT sync_jobs_source_surface_check
              CHECK (source_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'sync_jobs_target_surface_check'
          ) THEN
            ALTER TABLE sync_jobs
              ADD CONSTRAINT sync_jobs_target_surface_check
              CHECK (target_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'threads_priority_check'
          ) THEN
            ALTER TABLE threads
              ADD CONSTRAINT threads_priority_check
              CHECK (priority IN ('low', 'med', 'high', 'urgent'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'threads_visibility_check'
          ) THEN
            ALTER TABLE threads
              ADD CONSTRAINT threads_visibility_check
              CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'threads_freshness_state_check'
          ) THEN
            ALTER TABLE threads
              ADD CONSTRAINT threads_freshness_state_check
              CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'threads_review_status_check'
          ) THEN
            ALTER TABLE threads
              ADD CONSTRAINT threads_review_status_check
              CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale'))
              NOT VALID;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'scenes_placement_check'
          ) THEN
            ALTER TABLE scenes
              ADD CONSTRAINT scenes_placement_check
              CHECK (placement IN ('ordered', 'floating', 'backlog'))
              NOT VALID;
          END IF;
        END $$;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE scenes DROP CONSTRAINT IF EXISTS scenes_placement_check;
        ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_review_status_check;
        ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_freshness_state_check;
        ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_visibility_check;
        ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_priority_check;
        ALTER TABLE sync_jobs DROP CONSTRAINT IF EXISTS sync_jobs_target_surface_check;
        ALTER TABLE sync_jobs DROP CONSTRAINT IF EXISTS sync_jobs_source_surface_check;
        ALTER TABLE sync_jobs DROP CONSTRAINT IF EXISTS sync_jobs_status_check;
        ALTER TABLE sync_reviews DROP CONSTRAINT IF EXISTS sync_reviews_review_status_check;
        ALTER TABLE sync_reviews DROP CONSTRAINT IF EXISTS sync_reviews_target_surface_check;
        ALTER TABLE sync_reviews DROP CONSTRAINT IF EXISTS sync_reviews_source_surface_check;

        ALTER TABLE sync_jobs
          ALTER COLUMN status SET DEFAULT 'pending';
        """
    )
