"""Add session status column with CHECK constraint

Revision ID: 002
Revises: 001
Create Date: 2026-06-27 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add CHECK constraint to the status column in sessions table
    op.execute(
        sa.text(
            "ALTER TABLE sessions ADD CONSTRAINT sessions_status_check "
            "CHECK (status IN ('Planned', 'Active', 'Played'))"
        )
    )


def downgrade():
    # Drop the CHECK constraint
    op.execute(sa.text("ALTER TABLE sessions DROP CONSTRAINT sessions_status_check"))
