"""Add stable graph endpoint identifiers

Revision ID: 008
Revises: 007
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE threads
          ADD COLUMN IF NOT EXISTS graph_endpoint_id text NOT NULL DEFAULT '';
        UPDATE threads
        SET graph_endpoint_id = 'thread:' || id
        WHERE graph_endpoint_id = '';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_threads_graph_endpoint_id
          ON threads(graph_endpoint_id);

        ALTER TABLE sessions
          ADD COLUMN IF NOT EXISTS graph_endpoint_id text NOT NULL DEFAULT '';
        UPDATE sessions
        SET graph_endpoint_id = 'session:' || id::text
        WHERE graph_endpoint_id = '';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_graph_endpoint_id
          ON sessions(graph_endpoint_id);

        ALTER TABLE scenes
          ADD COLUMN IF NOT EXISTS graph_endpoint_id text NOT NULL DEFAULT '';
        UPDATE scenes
        SET graph_endpoint_id = 'scene:' || id::text
        WHERE graph_endpoint_id = '';
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
        """
    )


def downgrade():
    op.execute(
        """
        DROP TRIGGER IF EXISTS set_scenes_graph_endpoint_id ON scenes;
        DROP TRIGGER IF EXISTS set_sessions_graph_endpoint_id ON sessions;
        DROP TRIGGER IF EXISTS set_threads_graph_endpoint_id ON threads;
        DROP FUNCTION IF EXISTS set_graph_endpoint_id();
        DROP INDEX IF EXISTS uq_scenes_graph_endpoint_id;
        DROP INDEX IF EXISTS uq_sessions_graph_endpoint_id;
        DROP INDEX IF EXISTS uq_threads_graph_endpoint_id;
        ALTER TABLE scenes DROP COLUMN IF EXISTS graph_endpoint_id;
        ALTER TABLE sessions DROP COLUMN IF EXISTS graph_endpoint_id;
        ALTER TABLE threads DROP COLUMN IF EXISTS graph_endpoint_id;
        """
    )
