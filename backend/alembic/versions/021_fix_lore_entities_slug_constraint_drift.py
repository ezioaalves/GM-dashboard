"""Reconcile lore_entities' slug uniqueness with models.py/migration 004

Revision ID: 021
Revises: 020
Create Date: 2026-07-11 00:00:00.000000

Production has `UNIQUE (slug)` on `lore_entities`, matching migration 004's
`slug text NOT NULL UNIQUE` and `models.py`'s `slug = Column(Text,
nullable=False, unique=True)`. Some local/dev databases instead carry a
`UNIQUE (entity_type, slug)` constraint that was never created by any
migration in this repo — undocumented drift, likely a manual `ALTER TABLE`
from early prototyping of `_apply_vault_import`'s `ON CONFLICT` target that
was never turned into a migration. `sync_router.py`'s `_apply_vault_import`
was written against that drifted local constraint (`ON CONFLICT (entity_type,
slug)`), which doesn't exist in production, so every real `vault_import`
apply raised `psycopg2.errors.InvalidColumnReference`.

The code has been corrected to `ON CONFLICT (slug)` (the constraint that
actually exists in production and matches the models). This migration brings
any database missing the plain `slug` unique constraint in line, and drops
the undocumented composite one if present, so all environments match
`models.py` and this codebase's actual apply logic going forward.
"""
from alembic import op


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE lore_entities DROP CONSTRAINT IF EXISTS lore_entities_entity_type_slug_key"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_entities_slug_key'
          ) THEN
            ALTER TABLE lore_entities ADD CONSTRAINT lore_entities_slug_key UNIQUE (slug);
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE lore_entities DROP CONSTRAINT IF EXISTS lore_entities_slug_key"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'lore_entities_entity_type_slug_key'
          ) THEN
            ALTER TABLE lore_entities ADD CONSTRAINT lore_entities_entity_type_slug_key UNIQUE (entity_type, slug);
          END IF;
        END $$;
        """
    )
