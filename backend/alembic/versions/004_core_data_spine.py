"""Add core data spine tables

Revision ID: 004
Revises: 003
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE sync_jobs
          ADD COLUMN IF NOT EXISTS review_id uuid REFERENCES sync_reviews(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN IF NOT EXISTS result_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN IF NOT EXISTS error_code text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS error_message text NOT NULL DEFAULT '';

        UPDATE sync_jobs
        SET input_payload = payload
        WHERE input_payload = '{}'::jsonb AND payload <> '{}'::jsonb;

        UPDATE sync_jobs
        SET result_payload = result
        WHERE result_payload = '{}'::jsonb AND result <> '{}'::jsonb;

        UPDATE sync_jobs
        SET error_message = error
        WHERE error_message = '' AND error <> '';

        CREATE INDEX IF NOT EXISTS idx_sync_jobs_review_id
          ON sync_jobs(review_id);
        CREATE INDEX IF NOT EXISTS idx_sync_jobs_status_created
          ON sync_jobs(status, created_at DESC);

        CREATE TABLE IF NOT EXISTS threads (
          id text PRIMARY KEY,
          title text NOT NULL,
          status text NOT NULL,
          arc text,
          next_move text,
          clock_label text,
          clock_value integer,
          clock_max integer,
          factions text[],
          sessions integer[],
          vault_path text,
          body text,
          created_at timestamptz DEFAULT now(),
          updated_at timestamptz DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS npcs (
          id serial PRIMARY KEY,
          slug text NOT NULL UNIQUE,
          name text NOT NULL,
          role text,
          affiliation text,
          location text,
          status text,
          rank text,
          tags text[],
          narrative text,
          gm_secret text,
          relationship_to_pcs jsonb,
          stats jsonb,
          img_path text,
          vault_path text,
          foundry_actor_id_test text,
          foundry_actor_id_prod text,
          foundry_sync_locked boolean DEFAULT false,
          foundry_last_synced_at timestamptz,
          foundry_pending_import jsonb,
          created_at timestamptz DEFAULT now(),
          updated_at timestamptz DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS pcs (
          id serial PRIMARY KEY,
          slug text NOT NULL UNIQUE,
          name text NOT NULL,
          player text,
          level integer,
          classes jsonb,
          stats jsonb,
          narrative text,
          vault_path text,
          img_path text,
          foundry_actor_id_test text,
          foundry_actor_id_prod text,
          foundry_pending_import jsonb,
          foundry_last_synced_at timestamptz,
          created_at timestamptz DEFAULT now(),
          updated_at timestamptz DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS lore_sources (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          source_surface text NOT NULL DEFAULT 'vault',
          source_path text NOT NULL,
          source_hash text NOT NULL DEFAULT '',
          source_mtime timestamptz,
          source_kind text NOT NULL DEFAULT 'markdown',
          title text NOT NULL DEFAULT '',
          visibility text NOT NULL DEFAULT 'gm'
            CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown')),
          freshness_state text NOT NULL DEFAULT 'unknown'
            CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown')),
          review_status text NOT NULL DEFAULT 'pending'
            CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (source_surface, source_path)
        );

        CREATE TABLE IF NOT EXISTS lore_entities (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          slug text NOT NULL UNIQUE,
          title text NOT NULL,
          entity_type text NOT NULL DEFAULT 'article',
          summary text NOT NULL DEFAULT '',
          primary_source_id uuid REFERENCES lore_sources(id) ON DELETE SET NULL,
          source_path text NOT NULL DEFAULT '',
          source_hash text NOT NULL DEFAULT '',
          source_mtime timestamptz,
          visibility text NOT NULL DEFAULT 'gm'
            CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown')),
          freshness_state text NOT NULL DEFAULT 'unknown'
            CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown')),
          review_status text NOT NULL DEFAULT 'pending'
            CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS lore_sections (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          source_id uuid NOT NULL REFERENCES lore_sources(id) ON DELETE CASCADE,
          entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL,
          heading text NOT NULL DEFAULT '',
          body text NOT NULL DEFAULT '',
          section_order integer NOT NULL DEFAULT 0,
          heading_path text[] NOT NULL DEFAULT '{}',
          start_line integer,
          end_line integer,
          visibility text NOT NULL DEFAULT 'gm'
            CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown')),
          freshness_state text NOT NULL DEFAULT 'unknown'
            CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown')),
          review_status text NOT NULL DEFAULT 'pending'
            CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS lore_aliases (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          entity_id uuid NOT NULL REFERENCES lore_entities(id) ON DELETE CASCADE,
          alias text NOT NULL,
          alias_kind text NOT NULL DEFAULT 'name',
          locale text NOT NULL DEFAULT '',
          review_status text NOT NULL DEFAULT 'accepted'
            CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (entity_id, alias, alias_kind)
        );

        CREATE TABLE IF NOT EXISTS lore_relationships (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          source_type text NOT NULL
            CHECK (source_type IN ('entity', 'thread', 'session', 'scene', 'asset')),
          source_id text NOT NULL,
          target_type text NOT NULL
            CHECK (target_type IN ('entity', 'thread', 'session', 'scene', 'asset')),
          target_id text NOT NULL DEFAULT '',
          unresolved_target text NOT NULL DEFAULT '',
          relationship_type text NOT NULL,
          direction text NOT NULL DEFAULT 'directed'
            CHECK (direction IN ('directed', 'bidirectional', 'undirected')),
          provenance text NOT NULL DEFAULT 'manual'
            CHECK (provenance IN ('wikilink', 'mention', 'asset_embed', 'manual', 'foundry_import', 'ai_suggestion', 'system')),
          confidence double precision,
          context text NOT NULL DEFAULT '',
          visibility text NOT NULL DEFAULT 'gm'
            CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown')),
          freshness_state text NOT NULL DEFAULT 'unknown'
            CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown')),
          review_status text NOT NULL DEFAULT 'pending'
            CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CHECK (target_id <> '' OR unresolved_target <> '')
        );

        CREATE TABLE IF NOT EXISTS lore_assets (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          source_path text NOT NULL UNIQUE,
          source_hash text NOT NULL DEFAULT '',
          source_mtime timestamptz,
          asset_type text NOT NULL DEFAULT 'image',
          usage text NOT NULL DEFAULT 'reference',
          title text NOT NULL DEFAULT '',
          status text NOT NULL DEFAULT 'current',
          visibility text NOT NULL DEFAULT 'gm'
            CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown')),
          freshness_state text NOT NULL DEFAULT 'unknown'
            CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown')),
          mirror_state text NOT NULL DEFAULT 'not_mirrored'
            CHECK (mirror_state IN ('not_mirrored', 'mirrored', 'stale_mirror', 'missing_source', 'missing_mirror', 'rejected_variant', 'conflict', 'failed')),
          foundry_path text NOT NULL DEFAULT '',
          foundry_uuid text NOT NULL DEFAULT '',
          width integer,
          height integer,
          linked_entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL,
          review_status text NOT NULL DEFAULT 'pending'
            CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
          metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          last_checked_at timestamptz,
          last_mirrored_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );

        ALTER TABLE lore_sources
          ADD COLUMN IF NOT EXISTS source_surface text NOT NULL DEFAULT 'vault',
          ADD COLUMN IF NOT EXISTS source_path text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_hash text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS title text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sources' AND column_name = 'path'
          ) THEN
            UPDATE lore_sources
            SET source_path = COALESCE(NULLIF(source_path, ''), path);
          END IF;
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sources' AND column_name = 'content_hash'
          ) THEN
            UPDATE lore_sources
            SET source_hash = COALESCE(NULLIF(source_hash, ''), content_hash);
          END IF;
        END $$;

        ALTER TABLE lore_entities
          ADD COLUMN IF NOT EXISTS source_path text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_hash text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_mtime timestamptz,
          ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'gm',
          ADD COLUMN IF NOT EXISTS freshness_state text NOT NULL DEFAULT 'unknown',
          ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'pending',
          ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_entities' AND column_name = 'structured'
          ) THEN
            UPDATE lore_entities
            SET metadata = structured
            WHERE metadata = '{}'::jsonb;
          END IF;
        END $$;

        ALTER TABLE lore_sections
          ADD COLUMN IF NOT EXISTS body text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS section_order integer NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS heading_path text[] NOT NULL DEFAULT '{}',
          ADD COLUMN IF NOT EXISTS start_line integer,
          ADD COLUMN IF NOT EXISTS end_line integer,
          ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sections' AND column_name = 'markdown'
          ) THEN
            UPDATE lore_sections
            SET body = COALESCE(NULLIF(body, ''), markdown);
          END IF;
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sections' AND column_name = 'ordinal'
          ) THEN
            UPDATE lore_sections
            SET section_order = ordinal
            WHERE section_order = 0;
          END IF;
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_sections' AND column_name = 'source_start_line'
          ) THEN
            UPDATE lore_sections
            SET start_line = source_start_line,
                end_line = source_end_line;
          END IF;
        END $$;

        ALTER TABLE lore_aliases
          ADD COLUMN IF NOT EXISTS alias_kind text NOT NULL DEFAULT 'name',
          ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'accepted',
          ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
          ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

        ALTER TABLE lore_relationships DROP CONSTRAINT IF EXISTS lore_relationships_source_id_fkey;
        ALTER TABLE lore_relationships
          ALTER COLUMN source_id TYPE text USING source_id::text,
          ALTER COLUMN target_id TYPE text USING target_id::text;
        ALTER TABLE lore_relationships
          ADD COLUMN IF NOT EXISTS unresolved_target text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS direction text NOT NULL DEFAULT 'directed',
          ADD COLUMN IF NOT EXISTS provenance text NOT NULL DEFAULT 'manual',
          ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'gm',
          ADD COLUMN IF NOT EXISTS freshness_state text NOT NULL DEFAULT 'unknown',
          ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'pending',
          ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_relationships' AND column_name = 'source_entity_id'
          ) THEN
            UPDATE lore_relationships
            SET source_id = COALESCE(NULLIF(source_id, ''), source_entity_id::text, '');
          END IF;
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_relationships' AND column_name = 'target_entity_id'
          ) THEN
            UPDATE lore_relationships
            SET target_id = COALESCE(NULLIF(target_id, ''), target_entity_id::text, '');
          END IF;
        END $$;

        UPDATE lore_relationships
        SET source_type = COALESCE(source_type, 'entity'),
            target_type = COALESCE(target_type, 'entity'),
            relationship_type = COALESCE(relationship_type, 'mentions'),
            target_id = COALESCE(target_id, ''),
            unresolved_target = COALESCE(unresolved_target, '');

        ALTER TABLE lore_relationships
          ALTER COLUMN source_id SET NOT NULL,
          ALTER COLUMN target_id SET DEFAULT '',
          ALTER COLUMN target_id SET NOT NULL,
          ALTER COLUMN source_type SET NOT NULL,
          ALTER COLUMN target_type SET NOT NULL,
          ALTER COLUMN relationship_type SET NOT NULL;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_relationships' AND column_name = 'target_slug'
          ) THEN
            UPDATE lore_relationships
            SET unresolved_target = COALESCE(NULLIF(unresolved_target, ''), target_slug, target_title, '')
            WHERE target_id = '';
          END IF;
        END $$;

        ALTER TABLE lore_assets
          ADD COLUMN IF NOT EXISTS source_hash text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS asset_type text NOT NULL DEFAULT 'image',
          ADD COLUMN IF NOT EXISTS title text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'current',
          ADD COLUMN IF NOT EXISTS freshness_state text NOT NULL DEFAULT 'unknown',
          ADD COLUMN IF NOT EXISTS mirror_state text NOT NULL DEFAULT 'not_mirrored',
          ADD COLUMN IF NOT EXISTS foundry_path text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS foundry_uuid text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS linked_entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'pending',
          ADD COLUMN IF NOT EXISTS source_mtime timestamptz;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_assets'
              AND column_name = 'usage'
              AND udt_name = '_text'
          ) THEN
            ALTER TABLE lore_assets
              ALTER COLUMN usage TYPE text USING COALESCE(usage[1], 'reference');
          END IF;
        END $$;

        ALTER TABLE lore_assets
          ALTER COLUMN usage SET DEFAULT 'reference',
          ALTER COLUMN usage SET NOT NULL;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_assets' AND column_name = 'content_hash'
          ) THEN
            UPDATE lore_assets
            SET source_hash = COALESCE(NULLIF(source_hash, ''), content_hash);
          END IF;
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_assets' AND column_name = 'mirror_status'
          ) THEN
            UPDATE lore_assets
            SET mirror_state = COALESCE(NULLIF(mirror_state, ''), mirror_status, sync_status, 'not_mirrored');
          END IF;
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_assets' AND column_name = 'foundry_mirror_path'
          ) THEN
            UPDATE lore_assets
            SET foundry_path = COALESCE(NULLIF(foundry_path, ''), foundry_mirror_path);
          END IF;
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'lore_assets' AND column_name = 'entity_id'
          ) THEN
            UPDATE lore_assets
            SET linked_entity_id = entity_id
            WHERE linked_entity_id IS NULL;
          END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS idx_lore_sources_path
          ON lore_sources(source_path);
        CREATE INDEX IF NOT EXISTS idx_lore_entities_type_title
          ON lore_entities(entity_type, title);
        CREATE INDEX IF NOT EXISTS idx_lore_sections_source_order
          ON lore_sections(source_id, section_order);
        CREATE INDEX IF NOT EXISTS idx_lore_aliases_alias
          ON lore_aliases(alias);
        CREATE INDEX IF NOT EXISTS idx_lore_relationships_source
          ON lore_relationships(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_lore_relationships_target
          ON lore_relationships(target_type, target_id);
        CREATE INDEX IF NOT EXISTS idx_lore_relationships_review
          ON lore_relationships(review_status);
        CREATE INDEX IF NOT EXISTS idx_lore_assets_state
          ON lore_assets(mirror_state, freshness_state);

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

        ALTER TABLE sessions
          ADD COLUMN IF NOT EXISTS summary text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS prep_notes text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS wrap_notes text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_path text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_hash text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_mtime timestamptz,
          ADD COLUMN IF NOT EXISTS played_at timestamptz,
          ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'gm',
          ADD COLUMN IF NOT EXISTS freshness_state text NOT NULL DEFAULT 'unknown',
          ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'accepted';

        ALTER TABLE scenes
          ADD COLUMN IF NOT EXISTS placement text NOT NULL DEFAULT 'backlog',
          ADD COLUMN IF NOT EXISTS sort_order integer NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS body text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS clues jsonb NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN IF NOT EXISTS planned_outcome text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS actual_outcome text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS foundry_export_status text NOT NULL DEFAULT 'not_exported',
          ADD COLUMN IF NOT EXISTS foundry_journal_id text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_path text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS source_hash text NOT NULL DEFAULT '',
          ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'gm',
          ADD COLUMN IF NOT EXISTS freshness_state text NOT NULL DEFAULT 'unknown',
          ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'accepted';

        UPDATE scenes
        SET placement = CASE WHEN session_id IS NULL THEN 'backlog' ELSE 'floating' END
        WHERE placement = 'backlog' AND session_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_threads_freshness
          ON threads(freshness_state, status);
        CREATE INDEX IF NOT EXISTS idx_sessions_freshness
          ON sessions(freshness_state, status);
        CREATE INDEX IF NOT EXISTS idx_scenes_placement
          ON scenes(session_id, placement, sort_order);
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_scenes_placement;
        DROP INDEX IF EXISTS idx_sessions_freshness;
        DROP INDEX IF EXISTS idx_threads_freshness;
        DROP INDEX IF EXISTS idx_lore_assets_state;
        DROP INDEX IF EXISTS idx_lore_relationships_review;
        DROP INDEX IF EXISTS idx_lore_relationships_target;
        DROP INDEX IF EXISTS idx_lore_relationships_source;
        DROP INDEX IF EXISTS idx_lore_aliases_alias;
        DROP INDEX IF EXISTS idx_lore_sections_source_order;
        DROP INDEX IF EXISTS idx_lore_entities_type_title;
        DROP INDEX IF EXISTS idx_lore_sources_path;
        DROP TABLE IF EXISTS lore_assets;
        DROP TABLE IF EXISTS lore_relationships;
        DROP TABLE IF EXISTS lore_aliases;
        DROP TABLE IF EXISTS lore_sections;
        DROP TABLE IF EXISTS lore_entities;
        DROP TABLE IF EXISTS lore_sources;
        DROP INDEX IF EXISTS idx_sync_jobs_status_created;
        DROP INDEX IF EXISTS idx_sync_jobs_review_id;
        ALTER TABLE sync_jobs
          DROP COLUMN IF EXISTS error_message,
          DROP COLUMN IF EXISTS error_code,
          DROP COLUMN IF EXISTS result_payload,
          DROP COLUMN IF EXISTS input_payload,
          DROP COLUMN IF EXISTS review_id;
        """
    )
