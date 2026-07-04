"""Clock engine: clocks, clock_ticks, cascade_rules + thread clock migration

Revision ID: 016
Revises: 015
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS clocks (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          graph_endpoint_id text NOT NULL DEFAULT '',
          name text NOT NULL,
          description text NOT NULL DEFAULT '',
          kind text NOT NULL DEFAULT 'progress',
          segments integer NOT NULL,
          filled integer NOT NULL DEFAULT 0,
          segment_labels jsonb NOT NULL DEFAULT '[]'::jsonb,
          lifecycle text NOT NULL DEFAULT 'active',
          resolution text NOT NULL DEFAULT '',
          resolved_at timestamptz,
          origin text NOT NULL DEFAULT 'manual',
          foundry_clock_id_test text NOT NULL DEFAULT '',
          foundry_clock_id_prod text NOT NULL DEFAULT '',
          mirror_state text NOT NULL DEFAULT 'not_mirrored',
          last_mirrored_at timestamptz,
          visibility text NOT NULL DEFAULT 'gm',
          freshness_state text NOT NULL DEFAULT 'unknown',
          review_status text NOT NULL DEFAULT 'accepted',
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT clocks_name_check CHECK (name <> ''),
          CONSTRAINT clocks_kind_check CHECK (kind IN ('progress', 'countdown')),
          CONSTRAINT clocks_segments_check CHECK (segments BETWEEN 1 AND 32),
          CONSTRAINT clocks_filled_check CHECK (filled >= 0 AND filled <= segments),
          CONSTRAINT clocks_lifecycle_check
            CHECK (lifecycle IN ('active', 'resolved', 'abandoned')),
          CONSTRAINT clocks_origin_check
            CHECK (origin IN ('manual', 'thread_migration'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_clocks_graph_endpoint_id
          ON clocks(graph_endpoint_id);

        DROP TRIGGER IF EXISTS set_clocks_graph_endpoint_id ON clocks;
        CREATE TRIGGER set_clocks_graph_endpoint_id
        BEFORE INSERT ON clocks
        FOR EACH ROW
        EXECUTE FUNCTION set_graph_endpoint_id('clock');

        CREATE TABLE IF NOT EXISTS clock_ticks (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          clock_id uuid NOT NULL REFERENCES clocks(id) ON DELETE CASCADE,
          delta integer NOT NULL,
          filled_before integer NOT NULL,
          filled_after integer NOT NULL,
          reason text NOT NULL,
          caused_by text NOT NULL DEFAULT 'manual',
          rule_id uuid,
          trigger_fire_id uuid NOT NULL,
          hop_depth integer NOT NULL DEFAULT 0,
          created_by uuid REFERENCES users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT clock_ticks_delta_check CHECK (delta <> 0),
          CONSTRAINT clock_ticks_reason_check CHECK (reason <> ''),
          CONSTRAINT clock_ticks_caused_by_check CHECK (caused_by IN ('manual', 'rule', 'import', 'drift_adopt')),
          CONSTRAINT clock_ticks_hop_depth_check CHECK (hop_depth >= 0)
        );
        CREATE INDEX IF NOT EXISTS ix_clock_ticks_clock_id
          ON clock_ticks(clock_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_clock_ticks_fire
          ON clock_ticks(trigger_fire_id);

        CREATE TABLE IF NOT EXISTS cascade_rules (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name text NOT NULL UNIQUE,
          title text NOT NULL DEFAULT '',
          description text NOT NULL DEFAULT '',
          trigger_kind text NOT NULL DEFAULT 'manual',
          trigger_clock_id uuid REFERENCES clocks(id) ON DELETE CASCADE,
          trigger_event text,
          condition jsonb NOT NULL DEFAULT '{}'::jsonb,
          effects jsonb NOT NULL DEFAULT '[]'::jsonb,
          enabled boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT cascade_rules_name_check CHECK (name <> ''),
          CONSTRAINT cascade_rules_trigger_kind_check
            CHECK (trigger_kind IN ('manual', 'clock_event')),
          CONSTRAINT cascade_rules_trigger_event_check
            CHECK (trigger_event IS NULL OR trigger_event IN ('ticked', 'filled', 'emptied')),
          CONSTRAINT cascade_rules_clock_event_check
            CHECK (
              trigger_kind <> 'clock_event'
              OR (trigger_clock_id IS NOT NULL AND trigger_event IS NOT NULL)
            )
        );

        ALTER TABLE clock_ticks
          ADD CONSTRAINT clock_ticks_rule_fk
          FOREIGN KEY (rule_id) REFERENCES cascade_rules(id) ON DELETE SET NULL;

        ALTER TABLE pcs
          ADD COLUMN IF NOT EXISTS graph_endpoint_id text NOT NULL DEFAULT '';
        UPDATE pcs
        SET graph_endpoint_id = 'pc:' || slug
        WHERE graph_endpoint_id = '';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pcs_graph_endpoint_id
          ON pcs(graph_endpoint_id);

        -- Extend lore_relationships endpoint-type constraints (from 014) so
        -- 'clock' and 'pc' endpoints are accepted, matching GRAPH_ENDPOINT_TYPES.
        ALTER TABLE lore_relationships
          DROP CONSTRAINT IF EXISTS lore_relationships_source_type_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_target_type_check;
        ALTER TABLE lore_relationships
          ADD CONSTRAINT lore_relationships_source_type_check
          CHECK (source_type IN ('entity', 'thread', 'session', 'scene', 'asset', 'clock', 'pc'))
          NOT VALID;
        ALTER TABLE lore_relationships
          ADD CONSTRAINT lore_relationships_target_type_check
          CHECK (target_type IN ('entity', 'thread', 'session', 'scene', 'asset', 'clock', 'pc'))
          NOT VALID;

        -- Thread inline clock migration: one progress clock per thread with a label.
        WITH migrated AS (
          INSERT INTO clocks (name, kind, segments, filled, origin, lifecycle)
          SELECT
            t.clock_label,
            'progress',
            GREATEST(COALESCE(t.clock_max, 1), 1),
            LEAST(
              GREATEST(COALESCE(t.clock_value, 0), 0),
              GREATEST(COALESCE(t.clock_max, 1), 1)
            ),
            'thread_migration',
            CASE WHEN t.status IN ('resolved', 'paid') THEN 'resolved' ELSE 'active' END
          FROM threads t
          WHERE t.clock_label IS NOT NULL AND t.clock_label <> ''
          RETURNING id, graph_endpoint_id, name
        )
        INSERT INTO lore_relationships (
          source_type, source_id, target_type, target_id,
          relationship_type, direction, provenance, review_status, context
        )
        SELECT
          'clock', m.graph_endpoint_id, 'thread', t.graph_endpoint_id,
          'tracks', 'directed', 'system', 'accepted', 'migrated from thread inline clock'
        FROM migrated m
        JOIN threads t
          ON t.clock_label = m.name
          AND t.clock_label IS NOT NULL AND t.clock_label <> '';
        """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM lore_relationships WHERE source_type = 'clock';
        DELETE FROM lore_relationships
          WHERE target_type IN ('clock', 'pc') OR source_type = 'pc';
        DROP TABLE IF EXISTS clock_ticks;
        DROP TABLE IF EXISTS cascade_rules;
        DROP TABLE IF EXISTS clocks;
        DROP INDEX IF EXISTS uq_pcs_graph_endpoint_id;
        ALTER TABLE pcs DROP COLUMN IF EXISTS graph_endpoint_id;

        -- Restore the original (014) lore_relationships endpoint-type constraints.
        ALTER TABLE lore_relationships
          DROP CONSTRAINT IF EXISTS lore_relationships_source_type_check,
          DROP CONSTRAINT IF EXISTS lore_relationships_target_type_check;
        ALTER TABLE lore_relationships
          ADD CONSTRAINT lore_relationships_source_type_check
          CHECK (source_type IN ('entity', 'thread', 'session', 'scene', 'asset'))
          NOT VALID;
        ALTER TABLE lore_relationships
          ADD CONSTRAINT lore_relationships_target_type_check
          CHECK (target_type IN ('entity', 'thread', 'session', 'scene', 'asset'))
          NOT VALID;
        """
    )
