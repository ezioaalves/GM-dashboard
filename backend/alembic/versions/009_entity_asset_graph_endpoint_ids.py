"""Add entity and asset graph endpoint identifiers

Revision ID: 009
Revises: 008
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE lore_entities
          ADD COLUMN IF NOT EXISTS graph_endpoint_id text NOT NULL DEFAULT '';
        UPDATE lore_entities
        SET graph_endpoint_id = 'entity:' || id::text
        WHERE graph_endpoint_id = '';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_entities_graph_endpoint_id
          ON lore_entities(graph_endpoint_id);

        ALTER TABLE lore_assets
          ADD COLUMN IF NOT EXISTS graph_endpoint_id text NOT NULL DEFAULT '';
        UPDATE lore_assets
        SET graph_endpoint_id = 'asset:' || id::text
        WHERE graph_endpoint_id = '';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lore_assets_graph_endpoint_id
          ON lore_assets(graph_endpoint_id);

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
        """
    )


def downgrade():
    op.execute(
        """
        DROP TRIGGER IF EXISTS set_lore_assets_graph_endpoint_id ON lore_assets;
        DROP TRIGGER IF EXISTS set_lore_entities_graph_endpoint_id ON lore_entities;
        DROP INDEX IF EXISTS uq_lore_assets_graph_endpoint_id;
        DROP INDEX IF EXISTS uq_lore_entities_graph_endpoint_id;
        ALTER TABLE lore_assets DROP COLUMN IF EXISTS graph_endpoint_id;
        ALTER TABLE lore_entities DROP COLUMN IF EXISTS graph_endpoint_id;
        """
    )
