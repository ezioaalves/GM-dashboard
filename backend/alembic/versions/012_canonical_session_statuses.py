"""Canonical session status values

Revision ID: 012
Revises: 011
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE sessions
          DROP CONSTRAINT IF EXISTS sessions_status_check;

        UPDATE sessions
        SET status = CASE status
          WHEN 'Planned' THEN 'planned'
          WHEN 'Active' THEN 'ready'
          WHEN 'Played' THEN 'played'
          ELSE status
        END;

        ALTER TABLE sessions
          ALTER COLUMN status SET DEFAULT 'planned';

        ALTER TABLE sessions
          ADD CONSTRAINT sessions_status_check
          CHECK (status IN ('planned', 'ready', 'played', 'cancelled', 'archived'));
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE sessions
          DROP CONSTRAINT IF EXISTS sessions_status_check;

        UPDATE sessions
        SET status = CASE status
          WHEN 'planned' THEN 'Planned'
          WHEN 'ready' THEN 'Active'
          WHEN 'played' THEN 'Played'
          WHEN 'cancelled' THEN 'Planned'
          WHEN 'archived' THEN 'Played'
          ELSE status
        END;

        ALTER TABLE sessions
          ALTER COLUMN status SET DEFAULT 'Planned';

        ALTER TABLE sessions
          ADD CONSTRAINT sessions_status_check
          CHECK (status IN ('Planned', 'Active', 'Played'));
        """
    )
