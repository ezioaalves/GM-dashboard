"""Add thread direction fields

Revision ID: 011
Revises: 010
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE threads
          ADD COLUMN IF NOT EXISTS priority text NOT NULL DEFAULT 'med',
          ADD COLUMN IF NOT EXISTS theme text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS pressure text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS stakes text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS unresolved_questions text[] NOT NULL DEFAULT '{}',
          ADD COLUMN IF NOT EXISTS last_touched_at timestamptz,
          ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'gm',
          ADD COLUMN IF NOT EXISTS freshness_state text NOT NULL DEFAULT 'unknown',
          ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'accepted';

        UPDATE threads
        SET graph_endpoint_id = 'thread:' || id
        WHERE graph_endpoint_id = '';

        CREATE INDEX IF NOT EXISTS idx_threads_freshness
          ON threads(freshness_state, status);
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_threads_freshness;
        ALTER TABLE threads
          DROP COLUMN IF EXISTS review_status,
          DROP COLUMN IF EXISTS freshness_state,
          DROP COLUMN IF EXISTS visibility,
          DROP COLUMN IF EXISTS last_touched_at,
          DROP COLUMN IF EXISTS unresolved_questions,
          DROP COLUMN IF EXISTS stakes,
          DROP COLUMN IF EXISTS pressure,
          DROP COLUMN IF EXISTS theme,
          DROP COLUMN IF EXISTS priority;
        """
    )
