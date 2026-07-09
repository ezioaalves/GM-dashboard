"""Campaign layer: PC lanes, risk register, feedback tracker

Revision ID: 019
Revises: 018
Create Date: 2026-07-09 00:00:00.000000

"""
from alembic import op


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pc_lanes (
          id                    serial PRIMARY KEY,
          pc_id                 integer NOT NULL UNIQUE REFERENCES pcs(id) ON DELETE CASCADE,
          goal                  text NOT NULL DEFAULT '',
          status                text NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'stalled', 'resolved', 'shelved')),
          pressure              text NOT NULL DEFAULT '',
          notes                 text NOT NULL DEFAULT '',
          last_touched_session  integer,
          created_at            timestamptz NOT NULL DEFAULT now(),
          updated_at            timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS risks (
          id                     serial PRIMARY KEY,
          title                  text NOT NULL DEFAULT '',
          description            text NOT NULL DEFAULT '',
          likelihood             text NOT NULL DEFAULT 'medium'
            CHECK (likelihood IN ('low', 'medium', 'high')),
          mitigation             text NOT NULL DEFAULT '',
          contingency            text NOT NULL DEFAULT '',
          status                 text NOT NULL DEFAULT 'open'
            CHECK (status IN ('open', 'mitigated', 'triggered', 'closed')),
          related_thread_id      text REFERENCES threads(id) ON DELETE SET NULL,
          related_pc_id          integer REFERENCES pcs(id) ON DELETE SET NULL,
          last_reviewed_session  integer,
          created_at             timestamptz NOT NULL DEFAULT now(),
          updated_at             timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_risks_last_reviewed
          ON risks(last_reviewed_session);

        CREATE TABLE IF NOT EXISTS feedback_entries (
          id              serial PRIMARY KEY,
          session_number  integer,
          cadence         text NOT NULL DEFAULT 'quick_check'
            CHECK (cadence IN ('quick_check', 'arc_review', 'private_checkin')),
          players_present text NOT NULL DEFAULT '',
          more_of         text NOT NULL DEFAULT '',
          less_of         text NOT NULL DEFAULT '',
          clarify         text NOT NULL DEFAULT '',
          notes           text NOT NULL DEFAULT '',
          recorded_at     date NOT NULL DEFAULT CURRENT_DATE,
          created_at      timestamptz NOT NULL DEFAULT now(),
          updated_at      timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_entries_session_number
          ON feedback_entries(session_number);

        CREATE TABLE IF NOT EXISTS feedback_action_items (
          id           serial PRIMARY KEY,
          feedback_id  integer NOT NULL REFERENCES feedback_entries(id) ON DELETE CASCADE,
          item         text NOT NULL DEFAULT '',
          owner        text NOT NULL DEFAULT '',
          follow_up    text NOT NULL DEFAULT '',
          status       text NOT NULL DEFAULT 'open'
            CHECK (status IN ('open', 'done', 'dropped')),
          sort_order   integer NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_action_items_feedback
          ON feedback_action_items(feedback_id, sort_order);
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS feedback_action_items;
        DROP TABLE IF EXISTS feedback_entries;
        DROP TABLE IF EXISTS risks;
        DROP TABLE IF EXISTS pc_lanes;
        """
    )
