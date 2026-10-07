"""Add admin access flags to users.

Revision ID: 009_super_admin_access
Revises: 008_budget_direct_funding
"""

from alembic import op
import sqlalchemy as sa


revision = "009_super_admin_access"
down_revision = "008_budget_direct_funding"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("is_super_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("has_test_access", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index("ix_user_is_admin", ["is_admin"], unique=False)
        batch_op.create_index("ix_user_is_super_admin", ["is_super_admin"], unique=False)
        batch_op.create_index("ix_user_has_test_access", ["has_test_access"], unique=False)

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("is_admin", server_default=None)
        batch_op.alter_column("is_super_admin", server_default=None)
        batch_op.alter_column("has_test_access", server_default=None)


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_has_test_access")
        batch_op.drop_index("ix_user_is_super_admin")
        batch_op.drop_index("ix_user_is_admin")
        batch_op.drop_column("has_test_access")
        batch_op.drop_column("is_super_admin")
        batch_op.drop_column("is_admin")
