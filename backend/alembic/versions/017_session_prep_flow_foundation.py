"""Session prep flow foundation fields

Revision ID: 017
Revises: 016
Create Date: 2026-07-05 00:00:00.000000

"""
from alembic import op


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE sessions
          ADD COLUMN IF NOT EXISTS promise text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS fit_check jsonb NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN IF NOT EXISTS clue_map jsonb NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN IF NOT EXISTS wrap_capture jsonb NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN IF NOT EXISTS recap_seed text NOT NULL DEFAULT '';

        ALTER TABLE scenes
          ADD COLUMN IF NOT EXISTS scene_type text NOT NULL DEFAULT 'soft',
          ADD COLUMN IF NOT EXISTS cut_or_replace_plan text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS planned_notes text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS actual_notes text NOT NULL DEFAULT '';

        UPDATE scenes
        SET scene_type = CASE
          WHEN lower(type) IN ('hard', 'core') THEN 'hard'
          WHEN lower(type) IN ('soft', 'supplemental') THEN 'soft'
          WHEN lower(type) = 'cut' THEN 'cut'
          WHEN lower(type) IN ('added', 'extra') THEN 'added'
          WHEN lower(type) = 'replacement' THEN 'replacement'
          WHEN lower(type) = 'spotlight' THEN 'spotlight'
          WHEN lower(type) = 'bridge' THEN 'bridge'
          ELSE 'soft'
        END
        WHERE scene_type = '' OR scene_type IS NULL;

        UPDATE scenes
        SET cut_or_replace_plan = replacement_route
        WHERE cut_or_replace_plan = '' AND replacement_route <> '';

        ALTER TABLE scenes
          DROP CONSTRAINT IF EXISTS scenes_scene_type_check;
        ALTER TABLE scenes
          ADD CONSTRAINT scenes_scene_type_check
          CHECK (scene_type IN ('hard', 'soft', 'cut', 'added', 'replacement', 'spotlight', 'bridge'))
          NOT VALID;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE scenes
          DROP CONSTRAINT IF EXISTS scenes_scene_type_check,
          DROP COLUMN IF EXISTS actual_notes,
          DROP COLUMN IF EXISTS planned_notes,
          DROP COLUMN IF EXISTS cut_or_replace_plan,
          DROP COLUMN IF EXISTS scene_type;

        ALTER TABLE sessions
          DROP COLUMN IF EXISTS recap_seed,
          DROP COLUMN IF EXISTS wrap_capture,
          DROP COLUMN IF EXISTS clue_map,
          DROP COLUMN IF EXISTS fit_check,
          DROP COLUMN IF EXISTS promise;
        """
    )
