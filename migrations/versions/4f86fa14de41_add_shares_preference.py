"""add shares preference column

Revision ID: 4f86fa14de41
Revises: f7a6b5c4d3e2
"""

import sqlalchemy as sa
from alembic import op

revision = "4f86fa14de41"
down_revision = "f7a6b5c4d3e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notification_preferences",
        sa.Column("shares", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    with op.batch_alter_table("notification_preferences", schema=None) as batch_op:
        batch_op.alter_column("shares", server_default=None)


def downgrade():
    with op.batch_alter_table("notification_preferences", schema=None) as batch_op:
        batch_op.drop_column("shares")
