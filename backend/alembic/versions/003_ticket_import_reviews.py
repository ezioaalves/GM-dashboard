"""Add ticket import review spine

Revision ID: 003
Revises: 002
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE sync_jobs
          ADD COLUMN IF NOT EXISTS job_type text NOT NULL DEFAULT 'legacy',
          ADD COLUMN IF NOT EXISTS source_surface text NOT NULL DEFAULT 'manual',
          ADD COLUMN IF NOT EXISTS target_surface text NOT NULL DEFAULT 'manual',
          ADD COLUMN IF NOT EXISTS payload jsonb NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN IF NOT EXISTS result jsonb NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN IF NOT EXISTS error text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now(),
          ADD COLUMN IF NOT EXISTS started_at timestamptz,
          ADD COLUMN IF NOT EXISTS finished_at timestamptz;

        ALTER TABLE tickets
          ADD COLUMN IF NOT EXISTS lane text DEFAULT 'next',
          ADD COLUMN IF NOT EXISTS classification text DEFAULT '',
          ADD COLUMN IF NOT EXISTS target_epic text DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_path text DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_hash text DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_mtime timestamptz,
          ADD COLUMN IF NOT EXISTS review_status text DEFAULT 'accepted';

        UPDATE tickets
        SET lane = stage
        WHERE lane IS NULL OR lane = '';

        CREATE TABLE IF NOT EXISTS sync_reviews (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          review_type text NOT NULL,
          source_surface text NOT NULL,
          target_surface text NOT NULL,
          target_type text NOT NULL,
          target_id text NOT NULL DEFAULT '',
          base_version text NOT NULL DEFAULT '',
          current_version text NOT NULL DEFAULT '',
          proposed_changes jsonb NOT NULL DEFAULT '{}'::jsonb,
          conflict_flags jsonb NOT NULL DEFAULT '[]'::jsonb,
          review_status text NOT NULL DEFAULT 'pending'
            CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
          decision jsonb NOT NULL DEFAULT '{}'::jsonb,
          sync_job_id uuid REFERENCES sync_jobs(id) ON DELETE SET NULL,
          created_by uuid REFERENCES users(id),
          updated_by uuid REFERENCES users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          decided_at timestamptz,
          applied_at timestamptz
        );

        CREATE INDEX IF NOT EXISTS idx_sync_reviews_status_created
          ON sync_reviews(review_status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sync_reviews_target
          ON sync_reviews(target_type, target_id);
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_sync_reviews_target;
        DROP INDEX IF EXISTS idx_sync_reviews_status_created;
        DROP TABLE IF EXISTS sync_reviews;
        """
    )
