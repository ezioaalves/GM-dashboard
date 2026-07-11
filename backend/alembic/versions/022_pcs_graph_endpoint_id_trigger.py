"""Add missing graph_endpoint_id auto-populate trigger on pcs

Revision ID: 022
Revises: 021
Create Date: 2026-07-11 00:00:00.000000

Migration 016 added `graph_endpoint_id` + a `UNIQUE` index to `pcs` and
backfilled existing rows, but — unlike every other table that got this
treatment (threads/sessions/scenes in 008, and others since) — never added
the `BEFORE INSERT` trigger that auto-populates `graph_endpoint_id` for new
rows. New `pcs` inserts (via `sheet_scan.sync_pc_sheets`) fell back to the
column's `''` default, so the second PC ever synced hit
`uq_pcs_graph_endpoint_id` and raised `UniqueViolation` — PC sync silently
broke after the first row. This reuses the existing `set_graph_endpoint_id()`
function (from migration 008) the same way the other tables use it.
"""
from alembic import op


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS set_pcs_graph_endpoint_id ON pcs;
        CREATE TRIGGER set_pcs_graph_endpoint_id
        BEFORE INSERT ON pcs
        FOR EACH ROW
        EXECUTE FUNCTION set_graph_endpoint_id('pc');
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS set_pcs_graph_endpoint_id ON pcs")
