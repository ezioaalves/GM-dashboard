# ONE-SHOT MIGRATION — DO NOT RE-RUN WITH PRODUCTION DATA
# The scenes table is dropped and recreated. Re-running this script
# will destroy all scene records. Apply it once on a fresh DB only.
from __future__ import annotations
import os
import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://kaihou_gm:kaihou_gm_dev@localhost:54329/kaihou_gm"
)

DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    number      INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Drops scenes unconditionally — safe on first run, destructive on re-run.
-- See file header warning above before executing.
DROP TABLE IF EXISTS scenes;

CREATE TABLE scenes (
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
"""

if __name__ == "__main__":
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.close()
    print("Migration complete.")
