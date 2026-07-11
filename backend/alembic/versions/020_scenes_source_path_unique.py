"""Add partial unique index on scenes.source_path for event import upsert

Revision ID: 020
Revises: 019
Create Date: 2026-07-11 00:00:00.000000

`source_path` defaults to '' for scenes authored directly in the dashboard
(not synced from the vault), so a plain unique constraint would break
ordinary scene creation the moment a second empty-path scene is inserted.
Scope the uniqueness to non-empty source paths only, which is what the
Event Library import (event_scan.py) relies on for its `ON CONFLICT
(source_path)` upsert.
"""
from alembic import op


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_scenes_source_path
          ON scenes(source_path)
          WHERE source_path <> ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_scenes_source_path")
