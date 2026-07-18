"""Campaign arcs, ideas, truths, scoped AI proposals, and alias safety metadata.

Revision ID: 023
Revises: 022
"""
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE lore_aliases ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'gm';
    ALTER TABLE lore_aliases ADD COLUMN IF NOT EXISTS temporal_context text NOT NULL DEFAULT '';
    ALTER TABLE lore_aliases DROP CONSTRAINT IF EXISTS lore_aliases_visibility_check;
    ALTER TABLE lore_aliases ADD CONSTRAINT lore_aliases_visibility_check
      CHECK (visibility IN ('gm','player','mixed','unknown'));

    CREATE TABLE IF NOT EXISTS campaign_arcs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), slug text NOT NULL UNIQUE,
      title text NOT NULL, status text NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned','active','completed','archived')),
      current boolean NOT NULL DEFAULT false, summary text NOT NULL DEFAULT '',
      current_adventure_id integer REFERENCES adventures(id) ON DELETE SET NULL,
      current_session_id integer REFERENCES sessions(id) ON DELETE SET NULL,
      visibility text NOT NULL DEFAULT 'gm'
        CHECK (visibility IN ('gm','player','mixed','unknown')),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_campaign_arcs_current ON campaign_arcs(current) WHERE current;

    CREATE TABLE IF NOT EXISTS creative_ideas (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), title text NOT NULL,
      body text NOT NULL DEFAULT '', state text NOT NULL DEFAULT 'captured'
        CHECK (state IN ('captured','triaged','promoted','discarded')),
      source text NOT NULL DEFAULT 'quick_capture', arc_id uuid REFERENCES campaign_arcs(id) ON DELETE SET NULL,
      target jsonb NOT NULL DEFAULT '{}'::jsonb, visibility text NOT NULL DEFAULT 'gm'
        CHECK (visibility IN ('gm','player','mixed','unknown')),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS campaign_truths (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), key text NOT NULL UNIQUE, statement text NOT NULL,
      state text NOT NULL DEFAULT 'provisional'
        CHECK (state IN ('provisional','locked','contradicted','superseded')),
      context_policy text NOT NULL DEFAULT 'scoped'
        CHECK (context_policy IN ('always','scoped','explicit_only','never')),
      visibility text NOT NULL DEFAULT 'gm' CHECK (visibility IN ('gm','player','mixed','unknown')),
      temporal_context text NOT NULL DEFAULT 'current', source text NOT NULL DEFAULT 'manual',
      supersedes_id uuid REFERENCES campaign_truths(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS creative_proposals (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), title text NOT NULL, task text NOT NULL DEFAULT '',
      target_type text NOT NULL, target_id text NOT NULL DEFAULT '',
      state text NOT NULL DEFAULT 'draft'
        CHECK (state IN ('draft','pending_review','accepted','rejected','applied','superseded')),
      proposed_changes jsonb NOT NULL DEFAULT '{}'::jsonb, context_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
      context_checksum text NOT NULL DEFAULT '', target_surface text NOT NULL DEFAULT 'postgres',
      decision jsonb NOT NULL DEFAULT '{}'::jsonb, applied_audit_id uuid,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS campaign_arc_links (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), arc_id uuid NOT NULL REFERENCES campaign_arcs(id) ON DELETE CASCADE,
      source_type text NOT NULL, source_id text NOT NULL, relation text NOT NULL DEFAULT 'contains',
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (arc_id, source_type, source_id, relation)
    );
    CREATE TABLE IF NOT EXISTS creative_proposal_audits (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), proposal_id uuid NOT NULL REFERENCES creative_proposals(id) ON DELETE CASCADE,
      action text NOT NULL, actor text NOT NULL DEFAULT 'gm', result jsonb NOT NULL DEFAULT '{}'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now()
    );

    -- Establish the current operating cursor without fabricating played history.
    INSERT INTO adventures (title, status, current_arc, pitch, visibility)
      SELECT 'Kage Summit', 'ready', 'The Training Arc',
             'The next session begins at the ball.', 'gm'
      WHERE NOT EXISTS (SELECT 1 FROM adventures WHERE lower(title) = lower('Kage Summit'));
    INSERT INTO campaign_arcs (slug, title, status, current, summary, current_adventure_id)
      SELECT 'training-arc', 'The Training Arc', 'active', true,
             'Current arc; Kage Summit is the current adventure.', a.id
      FROM adventures a
      WHERE lower(a.title) = lower('Kage Summit')
        AND NOT EXISTS (SELECT 1 FROM campaign_arcs WHERE slug = 'training-arc');
    UPDATE campaign_arcs c
      SET current_adventure_id = a.id, current = true, status = 'active'
      FROM adventures a
      WHERE c.slug = 'training-arc' AND lower(a.title) = lower('Kage Summit');
    """)


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS creative_proposal_audits;
    DROP TABLE IF EXISTS campaign_arc_links;
    DROP TABLE IF EXISTS creative_proposals;
    DROP TABLE IF EXISTS campaign_truths;
    DROP TABLE IF EXISTS creative_ideas;
    DROP INDEX IF EXISTS uq_campaign_arcs_current;
    DROP TABLE IF EXISTS campaign_arcs;
    ALTER TABLE lore_aliases DROP COLUMN IF EXISTS temporal_context;
    ALTER TABLE lore_aliases DROP COLUMN IF EXISTS visibility;
    """)
