"""Add lore_entity_id forward-compat columns to npcs and pcs

Revision ID: 015
Revises: 014
Create Date: 2026-07-04 00:00:00.000000

"""
from alembic import op


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE npcs
          ADD COLUMN IF NOT EXISTS lore_entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL;
        ALTER TABLE pcs
          ADD COLUMN IF NOT EXISTS lore_entity_id uuid REFERENCES lore_entities(id) ON DELETE SET NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE pcs DROP COLUMN IF EXISTS lore_entity_id;
        ALTER TABLE npcs DROP COLUMN IF EXISTS lore_entity_id;
        """
    )
