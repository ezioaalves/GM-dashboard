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
  status text NOT NULL DEFAULT 'pending',
  diff text NOT NULL DEFAULT '',
  job_type text NOT NULL DEFAULT 'legacy',
  source_surface text NOT NULL DEFAULT 'manual',
  target_surface text NOT NULL DEFAULT 'manual',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text NOT NULL DEFAULT '',
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
  source_surface text NOT NULL,
  target_surface text NOT NULL,
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

CREATE TABLE IF NOT EXISTS sessions (
  id          SERIAL PRIMARY KEY,
  number      INTEGER NOT NULL UNIQUE,
  name        TEXT NOT NULL DEFAULT '',
  status      TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN ('Planned', 'Active', 'Played')),
  date        DATE,
  notes       TEXT NOT NULL DEFAULT '',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scenes (
  id                   SERIAL PRIMARY KEY,
  title                TEXT NOT NULL DEFAULT '',
  type                 TEXT NOT NULL DEFAULT '',
  status               TEXT NOT NULL DEFAULT 'Draft',
  session_id           INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
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
  pinned_material      JSONB NOT NULL DEFAULT '[]',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
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
