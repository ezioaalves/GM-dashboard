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
  promise     TEXT NOT NULL DEFAULT '',
  fit_check   JSONB NOT NULL DEFAULT '{}',
  clue_map    JSONB NOT NULL DEFAULT '[]',
  wrap_capture JSONB NOT NULL DEFAULT '{}',
  recap_seed  TEXT NOT NULL DEFAULT '',
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
  scene_type           TEXT NOT NULL DEFAULT 'soft' CHECK (scene_type IN ('hard', 'soft', 'cut', 'added', 'replacement', 'spotlight', 'bridge')),
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
  cut_or_replace_plan  TEXT NOT NULL DEFAULT '',
  if_succeed           TEXT NOT NULL DEFAULT '',
  if_fail              TEXT NOT NULL DEFAULT '',
  if_ignore            TEXT NOT NULL DEFAULT '',
  if_short             TEXT NOT NULL DEFAULT '',
  notes                TEXT NOT NULL DEFAULT '',
  body                 TEXT NOT NULL DEFAULT '',
  clues                JSONB NOT NULL DEFAULT '[]',
  planned_notes        TEXT NOT NULL DEFAULT '',
  actual_notes         TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS adventures (
  id                serial PRIMARY KEY,
  graph_endpoint_id text NOT NULL DEFAULT '',
  title             text NOT NULL DEFAULT '',
  status            text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'ready', 'played', 'archived')),
  current_arc       text NOT NULL DEFAULT '',
  pitch             text NOT NULL DEFAULT '',
  mode              text NOT NULL DEFAULT '',
  tone_rule         text NOT NULL DEFAULT '',
  safety_flags      text NOT NULL DEFAULT '',
  feel_target       text NOT NULL DEFAULT '',
  feel_avoid        text NOT NULL DEFAULT '',
  stakes            jsonb NOT NULL DEFAULT '{}'::jsonb,
  location          jsonb NOT NULL DEFAULT '{}'::jsonb,
  spine             jsonb NOT NULL DEFAULT '[]'::jsonb,
  clue_map          jsonb NOT NULL DEFAULT '{}'::jsonb,
  foundry_needs     jsonb NOT NULL DEFAULT '{}'::jsonb,
  rules_notes       jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_path       text NOT NULL DEFAULT '',
  source_hash       text NOT NULL DEFAULT '',
  source_mtime      timestamptz,
  visibility        text NOT NULL DEFAULT 'gm',
  freshness_state   text NOT NULL DEFAULT 'unknown',
  review_status     text NOT NULL DEFAULT 'accepted',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_adventures_graph_endpoint_id
  ON adventures(graph_endpoint_id);

DROP TRIGGER IF EXISTS set_adventures_graph_endpoint_id ON adventures;
CREATE TRIGGER set_adventures_graph_endpoint_id
BEFORE INSERT ON adventures
FOR EACH ROW
EXECUTE FUNCTION set_graph_endpoint_id('adventure');

CREATE TABLE IF NOT EXISTS adventure_pc_pressure (
  id           serial PRIMARY KEY,
  adventure_id integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
  pc_id        integer NOT NULL REFERENCES pcs(id),
  pressure     text NOT NULL DEFAULT '',
  growth       text NOT NULL DEFAULT '',
  cost         text NOT NULL DEFAULT '',
  sort_order   integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_adventure_pc_pressure_adventure
  ON adventure_pc_pressure(adventure_id, sort_order);

CREATE TABLE IF NOT EXISTS adventure_rewards (
  id               serial PRIMARY KEY,
  adventure_id     integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
  name             text NOT NULL DEFAULT '',
  type             text NOT NULL DEFAULT '',
  who_cares        text NOT NULL DEFAULT '',
  mechanical_note  text NOT NULL DEFAULT '',
  future_hook      text NOT NULL DEFAULT '',
  sort_order       integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_adventure_rewards_adventure
  ON adventure_rewards(adventure_id, sort_order);

CREATE TABLE IF NOT EXISTS adventure_clock_links (
  id               serial PRIMARY KEY,
  adventure_id     integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
  clock_id         uuid REFERENCES clocks(id) ON DELETE SET NULL,
  thread_id        text REFERENCES threads(id) ON DELETE SET NULL,
  how_it_appears   text NOT NULL DEFAULT '',
  advance_trigger  text NOT NULL DEFAULT '',
  visible_impact   text NOT NULL DEFAULT '',
  CONSTRAINT adventure_clock_links_target_check
    CHECK (clock_id IS NOT NULL OR thread_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_adventure_clock_links_adventure
  ON adventure_clock_links(adventure_id);

CREATE TABLE IF NOT EXISTS adventure_encounters (
  id                  serial PRIMARY KEY,
  adventure_id        integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
  name                text NOT NULL DEFAULT '',
  objective           text NOT NULL DEFAULT '',
  opposition          text NOT NULL DEFAULT '',
  terrain_constraint  text NOT NULL DEFAULT '',
  what_changes        text NOT NULL DEFAULT '',
  sort_order          integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_adventure_encounters_adventure
  ON adventure_encounters(adventure_id, sort_order);

CREATE TABLE IF NOT EXISTS adventure_cast (
  id           serial PRIMARY KEY,
  adventure_id integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
  npc_id       integer NOT NULL REFERENCES npcs(id),
  role         text NOT NULL DEFAULT '',
  wants_now    text NOT NULL DEFAULT '',
  hides        text NOT NULL DEFAULT '',
  if_helped    text NOT NULL DEFAULT '',
  if_crossed   text NOT NULL DEFAULT '',
  sort_order   integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_adventure_cast_adventure
  ON adventure_cast(adventure_id, sort_order);

CREATE TABLE IF NOT EXISTS session_adventures (
  session_id   integer NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  adventure_id integer NOT NULL REFERENCES adventures(id) ON DELETE CASCADE,
  PRIMARY KEY (session_id, adventure_id)
);

CREATE TABLE IF NOT EXISTS generator_tables (
  id    serial PRIMARY KEY,
  key   text NOT NULL UNIQUE,
  label text NOT NULL,
  die   text NOT NULL
);

CREATE TABLE IF NOT EXISTS generator_entries (
  id          serial PRIMARY KEY,
  table_id    integer NOT NULL REFERENCES generator_tables(id) ON DELETE CASCADE,
  roll        integer NOT NULL,
  name        text NOT NULL DEFAULT '',
  description text NOT NULL DEFAULT '',
  sort_order  integer NOT NULL DEFAULT 0,
  UNIQUE (table_id, roll)
);

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

INSERT INTO generator_tables (key, label, die) VALUES
  ('combat_type', 'Combat Type', 'd8'),
  ('combat_objective', 'Combat Objective', 'd12'),
  ('combat_tricks', 'Combat Tricks', 'd10'),
  ('mode_tag', 'Adventure Mode', 'd10')
ON CONFLICT (key) DO NOTHING;

INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
SELECT t.id, v.roll, v.name, v.description, v.roll
FROM generator_tables t
JOIN (VALUES
  (1, 'Skirmish', 'The most common and reliable type of combat. Fun and straightforward, but can become repetitive without clear objectives.'),
  (2, 'Ambush', 'Enemies find the party first, forcing a sudden, unpredictable adaptation.'),
  (3, 'Target Strike', 'The party gets the drop on a powerful foe; makes an otherwise impossible fight feel achievable.'),
  (4, 'Horde of Bad Guys', 'Massive numbers of weak enemies force resource-management decisions.'),
  (5, 'Elite Team', 'Named, powerful villains with unique roles; a bridge between skirmishes and boss battles.'),
  (6, 'Stomping Ground', 'An opportunity for the party to feel powerful and see how far they''ve come.'),
  (7, 'Boss Battle', 'High-stakes climax; maximally difficult, multi-phase.'),
  (8, 'Puzzle', 'Combat that is really a puzzle in disguise — disable a trap or race to an objective under fire.')
) AS v(roll, name, description) ON t.key = 'combat_type'
ON CONFLICT (table_id, roll) DO NOTHING;

INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
SELECT t.id, v.roll, v.name, v.description, v.roll
FROM generator_tables t
JOIN (VALUES
  (1, 'Deathmatch', 'The fight ends only when one side is defeated.'),
  (2, 'Stop the Ritual', 'Interrupt a ritual before it completes.'),
  (3, 'Daring Escape', 'Navigate through enemies to reach a safe point.'),
  (4, 'Hold the Fort', 'Defend a location for a set number of turns.'),
  (5, 'Waves of Bad Guys', 'Survive increasingly difficult or numerous waves.'),
  (6, 'Save the NPC', 'Protect an NPC the enemy may prioritize attacking.'),
  (7, 'Sabotage', 'Disable an enemy asset to ease a future encounter.'),
  (8, 'Escort the Thing', 'Move a precious or heavy item/NPC to a destination under threat.'),
  (9, 'Base Defense', 'Prevent the enemy from destroying or stealing key assets.'),
  (10, 'Yoink and Skedaddle', 'Steal an item and escape before raising an alarm.'),
  (11, 'Peace Makers', 'Stop a conflict between two hostile sides without becoming combatants.'),
  (12, 'The Arrest', 'Capture an enemy alive rather than killing them.')
) AS v(roll, name, description) ON t.key = 'combat_objective'
ON CONFLICT (table_id, roll) DO NOTHING;

INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
SELECT t.id, v.roll, v.name, v.description, v.roll
FROM generator_tables t
JOIN (VALUES
  (1, 'Red Barrels', 'Explosive hazards that encourage tactical positioning and area-of-effect combos.'),
  (2, 'Siege Weapons', 'Stationary cannons/ballistae that become a struggle for control.'),
  (3, 'Ammo Boxes', 'Crates with instantly usable loot or magic items.'),
  (4, 'Big Drops', 'Pits or cliffs for verticality and environmental kills.'),
  (5, 'Doors', 'Heavy, interactive doors that require an action, creating choke points.'),
  (6, 'Interactables', 'Levers or generic items that trigger map-wide changes.'),
  (7, 'Terrain', 'Difficult ground or hazards that force navigation choices.'),
  (8, 'Platforms', 'Moving elements that change the battlefield layout.'),
  (9, 'Lair Actions', 'Environmental boss-specific effects that work in synergy with antagonists.'),
  (10, '-', 'No trick this time.')
) AS v(roll, name, description) ON t.key = 'combat_tricks'
ON CONFLICT (table_id, roll) DO NOTHING;

INSERT INTO generator_entries (table_id, roll, name, description, sort_order)
SELECT t.id, v.roll, v.name, v.description, v.roll
FROM generator_tables t
JOIN (VALUES
  (1, 'Mission', 'Time, orders, terrain, and consequences matter.'),
  (2, 'Training', 'The challenge reveals who the PC is becoming.'),
  (3, 'Investigation', 'Core clues surface; rolls change leverage, speed, and cost.'),
  (4, 'Social/Court', 'Words have witnesses and future prices.'),
  (5, 'City Pressure', 'Violence is constrained by law, rank, clan, and rumor.'),
  (6, 'Underworld Favor', 'Access is useful, but every favor creates ownership pressure.'),
  (7, 'Clan Drama', 'Public identity and private desire collide.'),
  (8, 'Shadowlands Horror', 'Wonder and threat coexist; safety is never assumed.'),
  (9, 'Exam/Tournament', 'Skill matters, but interpretation by observers matters too.'),
  (10, 'Downtime Complication', 'The world moves while PCs optimize.')
) AS v(roll, name, description) ON t.key = 'mode_tag'
ON CONFLICT (table_id, roll) DO NOTHING;

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

-- Campaign truth / creative workflow (Alembic revision 023)
ALTER TABLE lore_aliases ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'gm';
ALTER TABLE lore_aliases ADD COLUMN IF NOT EXISTS temporal_context text NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS campaign_arcs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), slug text NOT NULL UNIQUE, title text NOT NULL,
  status text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','completed','archived')),
  current boolean NOT NULL DEFAULT false, summary text NOT NULL DEFAULT '',
  current_adventure_id integer REFERENCES adventures(id) ON DELETE SET NULL,
  current_session_id integer REFERENCES sessions(id) ON DELETE SET NULL,
  visibility text NOT NULL DEFAULT 'gm', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_campaign_arcs_current ON campaign_arcs(current) WHERE current;
CREATE TABLE IF NOT EXISTS creative_ideas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), title text NOT NULL, body text NOT NULL DEFAULT '',
  state text NOT NULL DEFAULT 'captured' CHECK (state IN ('captured','triaged','promoted','discarded')),
  source text NOT NULL DEFAULT 'quick_capture', arc_id uuid REFERENCES campaign_arcs(id) ON DELETE SET NULL,
  target jsonb NOT NULL DEFAULT '{}'::jsonb, visibility text NOT NULL DEFAULT 'gm', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS campaign_truths (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), key text NOT NULL UNIQUE, statement text NOT NULL,
  state text NOT NULL DEFAULT 'provisional' CHECK (state IN ('provisional','locked','contradicted','superseded')),
  context_policy text NOT NULL DEFAULT 'scoped' CHECK (context_policy IN ('always','scoped','explicit_only','never')),
  visibility text NOT NULL DEFAULT 'gm', temporal_context text NOT NULL DEFAULT 'current', source text NOT NULL DEFAULT 'manual',
  supersedes_id uuid REFERENCES campaign_truths(id) ON DELETE SET NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS creative_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), title text NOT NULL, task text NOT NULL DEFAULT '', target_type text NOT NULL,
  target_id text NOT NULL DEFAULT '', state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft','pending_review','accepted','rejected','applied','superseded')),
  proposed_changes jsonb NOT NULL DEFAULT '{}'::jsonb, context_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb, context_checksum text NOT NULL DEFAULT '',
  target_surface text NOT NULL DEFAULT 'postgres', decision jsonb NOT NULL DEFAULT '{}'::jsonb, applied_audit_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS campaign_arc_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), arc_id uuid NOT NULL REFERENCES campaign_arcs(id) ON DELETE CASCADE,
  source_type text NOT NULL, source_id text NOT NULL, relation text NOT NULL DEFAULT 'contains', created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (arc_id, source_type, source_id, relation)
);
CREATE TABLE IF NOT EXISTS creative_proposal_audits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), proposal_id uuid NOT NULL REFERENCES creative_proposals(id) ON DELETE CASCADE,
  action text NOT NULL, actor text NOT NULL DEFAULT 'gm', result jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
