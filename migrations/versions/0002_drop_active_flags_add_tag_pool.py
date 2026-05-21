"""drop is_active / is_active_employee, add tag_pool

Removes the unused account-active flags (a user is either present or
deleted) and adds the tag_pool table that recycles freed tag numbers.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_active")
    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_column("is_active_employee")
    op.create_table(
        "tag_pool",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tag_number", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tag_number"),
    )


def downgrade() -> None:
    op.drop_table("tag_pool")
    with op.batch_alter_table("user_profiles") as batch:
        batch.add_column(sa.Column("is_active_employee", sa.Boolean()))
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_active", sa.Boolean()))
