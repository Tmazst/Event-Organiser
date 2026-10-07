"""Add direct funding fields to budget categories.

Revision ID: 008_budget_direct_funding
Revises: 007_shared_identity_links
"""

from alembic import op
import sqlalchemy as sa


revision = "008_budget_direct_funding"
down_revision = "007_shared_identity_links"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("budget_category") as batch_op:
        batch_op.add_column(sa.Column("requires_quotation", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("funding_source", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("funding_source_name", sa.String(length=160), nullable=True))
    with op.batch_alter_table("budget_category") as batch_op:
        batch_op.alter_column("requires_quotation", server_default=None)


def downgrade():
    with op.batch_alter_table("budget_category") as batch_op:
        batch_op.drop_column("funding_source_name")
        batch_op.drop_column("funding_source")
        batch_op.drop_column("requires_quotation")
