"""baseline schema (pre-Alembic state)

This revision represents the schema as it existed before Alembic was
introduced. Databases that predate Alembic are stamped at this revision
instead of running it; it only executes in full on fresh databases.

Revision ID: 0001
Revises:
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=50), primary_key=True),
        sa.Column("value", sa.String(length=200)),
    )
    op.create_table(
        "asset_counter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254)),
        sa.Column("first_name", sa.String(length=150)),
        sa.Column("last_name", sa.String(length=150)),
        sa.Column("password_hash", sa.String(length=256)),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("is_superuser", sa.Boolean()),
        sa.Column("date_joined", sa.DateTime()),
        sa.Column("last_login", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
    )
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("phone", sa.String(length=30)),
        sa.Column("position", sa.String(length=100)),
        sa.Column("is_active_employee", sa.Boolean()),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text()),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_tag", sa.String(length=12), nullable=False),
        sa.Column("tag_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")),
        sa.Column("manufacturer", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("serial_number", sa.String(length=150), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("warranty_expiry", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20)),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_date", sa.Date(), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("location", sa.String(length=200)),
        sa.Column("notes", sa.Text()),
        sa.Column("cpu", sa.String(length=200)),
        sa.Column("ram", sa.String(length=100)),
        sa.Column("storage", sa.String(length=200)),
        sa.Column("phone_number", sa.String(length=50)),
        sa.Column("ink_type", sa.String(length=200)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_assets_asset_tag", "assets", ["asset_tag"], unique=True)
    op.create_index("ix_assets_tag_number", "assets", ["tag_number"], unique=True)
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_table(
        "licenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_tag", sa.String(length=12), nullable=False),
        sa.Column("tag_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("vendor", sa.String(length=100)),
        sa.Column("license_key", sa.String(length=500)),
        sa.Column("seats", sa.Integer()),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("status", sa.String(length=20)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_licenses_asset_tag", "licenses", ["asset_tag"], unique=True)
    op.create_index("ix_licenses_tag_number", "licenses", ["tag_number"], unique=True)
    op.create_index("ix_licenses_status", "licenses", ["status"])
    op.create_table(
        "license_users",
        sa.Column("license_id", sa.Integer(), sa.ForeignKey("licenses.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
    )
    op.create_table(
        "asset_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("license_id", sa.Integer(), sa.ForeignKey("licenses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("performed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("asset_history")
    op.drop_table("license_users")
    op.drop_index("ix_licenses_status", table_name="licenses")
    op.drop_index("ix_licenses_tag_number", table_name="licenses")
    op.drop_index("ix_licenses_asset_tag", table_name="licenses")
    op.drop_table("licenses")
    op.drop_index("ix_assets_status", table_name="assets")
    op.drop_index("ix_assets_tag_number", table_name="assets")
    op.drop_index("ix_assets_asset_tag", table_name="assets")
    op.drop_table("assets")
    op.drop_table("categories")
    op.drop_table("user_profiles")
    op.drop_table("departments")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("asset_counter")
    op.drop_table("settings")
