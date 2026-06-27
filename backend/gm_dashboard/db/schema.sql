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
  approved_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
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

