CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  display_name text NOT NULL,
  password_hash text NOT NULL,
  role text NOT NULL DEFAULT 'gm',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL,
  vault_path text,
  status text NOT NULL DEFAULT 'draft',
  markdown text NOT NULL DEFAULT '',
  source jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  source_path text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_mtime timestamptz,
  refreshed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS foundry_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vault_path text NOT NULL,
  foundry_uuid text NOT NULL,
  link_kind text NOT NULL,
  last_seen_at timestamptz,
  UNIQUE (vault_path, foundry_uuid)
);

CREATE TABLE IF NOT EXISTS sync_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target text NOT NULL,
  direction text NOT NULL,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'blocked', 'cancelled')),
  diff text NOT NULL DEFAULT '',
  job_type text NOT NULL DEFAULT 'legacy',
  source_surface text NOT NULL DEFAULT 'manual'
    CHECK (source_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual')),
  target_surface text NOT NULL DEFAULT 'manual'
    CHECK (target_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text NOT NULL DEFAULT '',
  review_id uuid,
  input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  result_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_code text NOT NULL DEFAULT '',
  error_message text NOT NULL DEFAULT '',
  approved_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  finished_at timestamptz,
  approved_at timestamptz
);

CREATE TABLE IF NOT EXISTS sheet_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  record_kind text NOT NULL,
  vault_path text,
  foundry_uuid text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tickets (
  id           TEXT PRIMARY KEY,
  title        TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open',
  area         TEXT NOT NULL,
  priority     TEXT NOT NULL DEFAULT 'med',
  stage        TEXT NOT NULL DEFAULT 'next',
  parent_id    TEXT REFERENCES tickets(id),
  threads      TEXT[] DEFAULT '{}',
  depends_on   TEXT[] DEFAULT '{}',
  next_action  TEXT DEFAULT '',
  resume_note  TEXT DEFAULT '',
  source       TEXT DEFAULT 'manual',
  introduced   DATE,
  closed       DATE,
  resolution   TEXT DEFAULT '',
  review_after DATE,
  lane         TEXT DEFAULT 'next',
  classification TEXT DEFAULT '',
  target_epic  TEXT DEFAULT '',
  source_path  TEXT DEFAULT '',
  source_hash  TEXT DEFAULT '',
  source_mtime TIMESTAMPTZ,
  review_status TEXT DEFAULT 'accepted',
  body         TEXT DEFAULT '',
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sync_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_type text NOT NULL,
  source_surface text NOT NULL
    CHECK (source_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual')),
  target_surface text NOT NULL
    CHECK (target_surface IN ('vault', 'postgres', 'foundry_test', 'foundry_prod', 'asset_fs', 'rag', 'vps', 'manual')),
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
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'sync_jobs_review_id_fkey'
  ) THEN
    ALTER TABLE sync_jobs
      ADD CONSTRAINT sync_jobs_review_id_fkey
      FOREIGN KEY (review_id) REFERENCES sync_reviews(id) ON DELETE SET NULL;
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_sync_jobs_review_id
  ON sync_jobs(review_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status_created
  ON sync_jobs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS threads (
  id text PRIMARY KEY,
  graph_endpoint_id text NOT NULL DEFAULT '',
  title text NOT NULL,
  status text NOT NULL,
  priority text NOT NULL DEFAULT 'med'
    CHECK (priority IN ('low', 'med', 'high', 'urgent')),
  arc text,
  theme text NOT NULL DEFAULT '',
  pressure text NOT NULL DEFAULT '',
  stakes text NOT NULL DEFAULT '',
  next_move text,
  clock_label text,
  clock_value integer,
  clock_max integer,
  unresolved_questions text[] NOT NULL DEFAULT '{}',
  last_touched_at timestamptz,
  visibility text NOT NULL DEFAULT 'gm'
    CHECK (visibility IN ('gm', 'player', 'mixed', 'unknown')),
  freshness_state text NOT NULL DEFAULT 'unknown'
    CHECK (freshness_state IN ('fresh', 'stale_source_changed', 'stale_db_newer', 'missing_source', 'missing_mirror', 'conflict', 'unknown')),
  review_status text NOT NULL DEFAULT 'accepted'
    CHECK (review_status IN ('pending', 'accepted', 'rejected', 'merged', 'deferred', 'conflict', 'stale')),
  factions text[],
  sessions integer[],
  vault_path text,
  body text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_threads_freshness
  ON threads(freshness_state, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_threads_graph_endpoint_id
  ON threads(graph_endpoint_id);

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
  lore_entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL,
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
  lore_entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL,
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
  visibility text NOT NULL DEFAULT 'gm',
  freshness_state text NOT NULL DEFAULT 'unknown',
  review_status text NOT NULL DEFAULT 'pending',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_surface, source_path)
);

CREATE TABLE IF NOT EXISTS lore_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  graph_endpoint_id text NOT NULL DEFAULT '',
  slug text NOT NULL UNIQUE,
  title text NOT NULL,
  entity_type text NOT NULL DEFAULT 'article',
  summary text NOT NULL DEFAULT '',
  primary_source_id uuid REFERENCES lore_sources(id) ON DELETE SET NULL,
  source_path text NOT NULL DEFAULT '',
  source_hash text NOT NULL DEFAULT '',
  source_mtime timestamptz,
  visibility text NOT NULL DEFAULT 'gm',
  freshness_state text NOT NULL DEFAULT 'unknown',
  review_status text NOT NULL DEFAULT 'pending',
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
  visibility text NOT NULL DEFAULT 'gm',
  freshness_state text NOT NULL DEFAULT 'unknown',
  review_status text NOT NULL DEFAULT 'pending',
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
  review_status text NOT NULL DEFAULT 'accepted',
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
  graph_endpoint_id text NOT NULL DEFAULT '',
  source_path text NOT NULL UNIQUE,
  source_hash text NOT NULL DEFAULT '',
  source_mtime timestamptz,
  asset_type text NOT NULL DEFAULT 'image',
  usage text NOT NULL DEFAULT 'reference',
  title text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'current',
  visibility text NOT NULL DEFAULT 'gm',
  freshness_state text NOT NULL DEFAULT 'unknown',
  mirror_state text NOT NULL DEFAULT 'not_mirrored',
  foundry_path text NOT NULL DEFAULT '',
  foundry_uuid text NOT NULL DEFAULT '',
  width integer,
  height integer,
  linked_entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL,
  review_status text NOT NULL DEFAULT 'pending',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_checked_at timestamptz,
  last_mirrored_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lore_sources_path
  ON lore_sources(source_path);
CREATE INDEX IF NOT EXISTS idx_lore_entities_type_title
  ON lore_entities(entity_type, title);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_entities_graph_endpoint_id
  ON lore_entities(graph_endpoint_id);
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_assets_graph_endpoint_id
  ON lore_assets(graph_endpoint_id);

CREATE TABLE IF NOT EXISTS sessions (
  id          SERIAL PRIMARY KEY,
  graph_endpoint_id TEXT NOT NULL DEFAULT '',
  number      INTEGER NOT NULL UNIQUE,
  name        TEXT NOT NULL DEFAULT '',
  status      TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'ready', 'played', 'cancelled', 'archived')),
  date        DATE,
  notes       TEXT NOT NULL DEFAULT '',
  summary     TEXT NOT NULL DEFAULT '',
  prep_notes  TEXT NOT NULL DEFAULT '',
  wrap_notes  TEXT NOT NULL DEFAULT '',
  source_path TEXT NOT NULL DEFAULT '',
  source_hash TEXT NOT NULL DEFAULT '',
  source_mtime TIMESTAMPTZ,
  played_at   TIMESTAMPTZ,
  visibility  TEXT NOT NULL DEFAULT 'gm',
  freshness_state TEXT NOT NULL DEFAULT 'unknown',
  review_status TEXT NOT NULL DEFAULT 'accepted',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scenes (
  id                   SERIAL PRIMARY KEY,
  graph_endpoint_id    TEXT NOT NULL DEFAULT '',
  title                TEXT NOT NULL DEFAULT '',
  type                 TEXT NOT NULL DEFAULT '',
  status               TEXT NOT NULL DEFAULT 'Draft',
  session_id           INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  placement            TEXT NOT NULL DEFAULT 'backlog' CHECK (placement IN ('ordered', 'floating', 'backlog')),
  sort_order           INTEGER NOT NULL DEFAULT 0,
  description          TEXT NOT NULL DEFAULT '',
  location             TEXT[] NOT NULL DEFAULT '{}',
  "cast"               TEXT[] NOT NULL DEFAULT '{}',
  "clock"              TEXT[] NOT NULL DEFAULT '{}',
  cuttable             BOOLEAN NOT NULL DEFAULT FALSE,
  purpose              TEXT NOT NULL DEFAULT '',
  pc_pressure          TEXT NOT NULL DEFAULT '',
  entry_pressure       TEXT NOT NULL DEFAULT '',
  exit_condition       TEXT NOT NULL DEFAULT '',
  core_clue            TEXT NOT NULL DEFAULT '',
  superior_clue        TEXT NOT NULL DEFAULT '',
  optional_clue        TEXT NOT NULL DEFAULT '',
  false_lead           TEXT NOT NULL DEFAULT '',
  opening_image        TEXT NOT NULL DEFAULT '',
  sensory_words        TEXT NOT NULL DEFAULT '',
  interactable_objects TEXT NOT NULL DEFAULT '',
  rules_likely         TEXT NOT NULL DEFAULT '',
  foundry_needs        TEXT NOT NULL DEFAULT '',
  replacement_route    TEXT NOT NULL DEFAULT '',
  if_succeed           TEXT NOT NULL DEFAULT '',
  if_fail              TEXT NOT NULL DEFAULT '',
  if_ignore            TEXT NOT NULL DEFAULT '',
  if_short             TEXT NOT NULL DEFAULT '',
  notes                TEXT NOT NULL DEFAULT '',
  body                 TEXT NOT NULL DEFAULT '',
  clues                JSONB NOT NULL DEFAULT '[]',
  planned_outcome      TEXT NOT NULL DEFAULT '',
  actual_outcome       TEXT NOT NULL DEFAULT '',
  foundry_export_status TEXT NOT NULL DEFAULT 'not_exported',
  foundry_journal_id   TEXT NOT NULL DEFAULT '',
  source_path          TEXT NOT NULL DEFAULT '',
  source_hash          TEXT NOT NULL DEFAULT '',
  visibility           TEXT NOT NULL DEFAULT 'gm',
  freshness_state      TEXT NOT NULL DEFAULT 'unknown',
  review_status        TEXT NOT NULL DEFAULT 'accepted',
  pinned_material      JSONB NOT NULL DEFAULT '[]',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessions_freshness
  ON sessions(freshness_state, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_graph_endpoint_id
  ON sessions(graph_endpoint_id);
CREATE INDEX IF NOT EXISTS idx_scenes_placement
  ON scenes(session_id, placement, sort_order);
CREATE UNIQUE INDEX IF NOT EXISTS uq_scenes_graph_endpoint_id
  ON scenes(graph_endpoint_id);

CREATE OR REPLACE FUNCTION set_graph_endpoint_id()
RETURNS trigger AS $$
BEGIN
  IF NEW.graph_endpoint_id IS NULL OR NEW.graph_endpoint_id = '' THEN
    NEW.graph_endpoint_id := TG_ARGV[0] || ':' || NEW.id::text;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_threads_graph_endpoint_id ON threads;
CREATE TRIGGER set_threads_graph_endpoint_id
BEFORE INSERT ON threads
FOR EACH ROW
EXECUTE FUNCTION set_graph_endpoint_id('thread');

DROP TRIGGER IF EXISTS set_lore_entities_graph_endpoint_id ON lore_entities;
CREATE TRIGGER set_lore_entities_graph_endpoint_id
BEFORE INSERT ON lore_entities
FOR EACH ROW
EXECUTE FUNCTION set_graph_endpoint_id('entity');

DROP TRIGGER IF EXISTS set_lore_assets_graph_endpoint_id ON lore_assets;
CREATE TRIGGER set_lore_assets_graph_endpoint_id
BEFORE INSERT ON lore_assets
FOR EACH ROW
EXECUTE FUNCTION set_graph_endpoint_id('asset');

DROP TRIGGER IF EXISTS set_sessions_graph_endpoint_id ON sessions;
CREATE TRIGGER set_sessions_graph_endpoint_id
BEFORE INSERT ON sessions
FOR EACH ROW
EXECUTE FUNCTION set_graph_endpoint_id('session');

DROP TRIGGER IF EXISTS set_scenes_graph_endpoint_id ON scenes;
CREATE TRIGGER set_scenes_graph_endpoint_id
BEFORE INSERT ON scenes
FOR EACH ROW
EXECUTE FUNCTION set_graph_endpoint_id('scene');

CREATE TABLE IF NOT EXISTS session_notes (
  id                   SERIAL PRIMARY KEY,
  session_id           INTEGER NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
  scenes               TEXT[] NOT NULL DEFAULT '{}',
  npcs_present         TEXT[] NOT NULL DEFAULT '{}',
  clues_discovered     TEXT[] NOT NULL DEFAULT '{}',
  threads_touched      TEXT[] NOT NULL DEFAULT '{}',
  unresolved_questions TEXT[] NOT NULL DEFAULT '{}',
  next_session_hook    TEXT NOT NULL DEFAULT '',
  memory               TEXT NOT NULL DEFAULT '',
  markdown             TEXT NOT NULL DEFAULT '',
  target_path          TEXT NOT NULL DEFAULT '',
  status               TEXT NOT NULL DEFAULT 'draft',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
