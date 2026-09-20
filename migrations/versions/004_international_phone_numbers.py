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

    # The original application stored validated Eswatini numbers without the
    # leading plus. Canonicalize them before new E.164 registrations are
    # accepted so the unique constraint still represents one real number.
    connection = op.get_bind()
    existing_users = connection.execute(
        sa.text("SELECT id, phone_number FROM user WHERE phone_number IS NOT NULL")
    ).mappings()
    for user in existing_users:
        digits = "".join(character for character in user["phone_number"] if character.isdigit())
        if len(digits) == 11 and digits.startswith("268"):
            connection.execute(
                sa.text("UPDATE user SET phone_number = :phone_number WHERE id = :user_id"),
                {"phone_number": f"+{digits}", "user_id": user["id"]},
            )


def downgrade():
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE user SET phone_number = substr(phone_number, 2) "
            "WHERE phone_number LIKE '+268%'"
        )
    )
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index("ix_user_phone_country")
        batch_op.drop_column("phone_country")
