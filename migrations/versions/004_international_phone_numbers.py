"""add international phone metadata

Revision ID: 004_international_phone_numbers
Revises: 003_event_profile_image
"""
from alembic import op
import sqlalchemy as sa


revision = "004_international_phone_numbers"
down_revision = "003_event_profile_image"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("phone_country", sa.String(length=2), nullable=False, server_default="SZ"))
        batch_op.create_index("ix_user_phone_country", ["phone_country"], unique=False)


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_phone_country")
        batch_op.drop_column("phone_country")
