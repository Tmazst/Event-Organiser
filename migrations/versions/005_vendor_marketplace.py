"""add vendor stores and product catalogues

Revision ID: 005_vendor_marketplace
Revises: 004_international_phone_numbers
"""
from alembic import op
import sqlalchemy as sa


revision = "005_vendor_marketplace"
down_revision = "004_international_phone_numbers"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("account_type", sa.String(length=20), nullable=False, server_default="organizer"))
        batch_op.create_index("ix_user_account_type", ["account_type"], unique=False)

    op.create_table(
        "vendor_store",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_name", sa.String(length=160), nullable=False),
        sa.Column("contact_phone", sa.String(length=40), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("offering_summary", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id"),
    )
    op.create_index("ix_vendor_store_store_name", "vendor_store", ["store_name"], unique=False)
    op.create_index("ix_vendor_store_location", "vendor_store", ["location"], unique=False)
    op.create_index("ix_vendor_store_owner_id", "vendor_store", ["owner_id"], unique=True)

    op.create_table(
        "vendor_product",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("price_unit", sa.String(length=60), nullable=True),
        sa.Column("publish_price", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["vendor_store.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vendor_product_name", "vendor_product", ["name"], unique=False)
    op.create_index("ix_vendor_product_store_id", "vendor_product", ["store_id"], unique=False)


def downgrade():
    op.drop_table("vendor_product")
    op.drop_table("vendor_store")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_account_type")
        batch_op.drop_column("account_type")
