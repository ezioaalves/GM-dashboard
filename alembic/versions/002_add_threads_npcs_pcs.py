"""Add threads, npcs, pcs tables.

Revision ID: 002
Revises: 001
Create Date: 2026-06-27
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "threads",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("arc", sa.Text()),
        sa.Column("next_move", sa.Text()),
        sa.Column("clock_label", sa.Text()),
        sa.Column("clock_value", sa.Integer()),
        sa.Column("clock_max", sa.Integer()),
        sa.Column("factions", ARRAY(sa.Text())),
        sa.Column("sessions", ARRAY(sa.Integer())),
        sa.Column("vault_path", sa.Text()),
        sa.Column("body", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "npcs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text()),
        sa.Column("affiliation", sa.Text()),
        sa.Column("location", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("rank", sa.Text()),
        sa.Column("tags", ARRAY(sa.Text())),
        sa.Column("narrative", sa.Text()),
        sa.Column("gm_secret", sa.Text()),
        sa.Column("relationship_to_pcs", JSONB()),
        sa.Column("stats", JSONB()),
        sa.Column("img_path", sa.Text()),
        sa.Column("vault_path", sa.Text()),
        sa.Column("foundry_actor_id_test", sa.Text()),
        sa.Column("foundry_actor_id_prod", sa.Text()),
        sa.Column("foundry_sync_locked", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("foundry_last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("foundry_pending_import", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "pcs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("player", sa.Text()),
        sa.Column("level", sa.Integer()),
        sa.Column("classes", JSONB()),
        sa.Column("stats", JSONB()),
        sa.Column("narrative", sa.Text()),
        sa.Column("vault_path", sa.Text()),
        sa.Column("img_path", sa.Text()),
        sa.Column("foundry_actor_id_test", sa.Text()),
        sa.Column("foundry_actor_id_prod", sa.Text()),
        sa.Column("foundry_pending_import", JSONB()),
        sa.Column("foundry_last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pcs")
    op.drop_table("npcs")
    op.drop_table("threads")
