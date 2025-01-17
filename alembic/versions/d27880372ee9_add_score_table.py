"""Add score table

Revision ID: d27880372ee9
Revises: df4e3586d014
Create Date: 2024-09-27 20:24:14.431231

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d27880372ee9"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    migration_users_table = op.create_table(
        "_migration_users",
        sa.Column(
            "id", sa.Integer(), autoincrement=True, nullable=False, primary_key=True
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=True),
        sa.Column("todoist_id", sa.String(), nullable=False),
        sa.Column("todoist_token", sa.String(), nullable=False),
    )

    connection = op.get_bind()
    users = connection.execute(sa.text("select * from users")).fetchall()

    users = [dict(user._mapping) for user in users]  # noqa: SLF001
    op.bulk_insert(migration_users_table, users)

    op.drop_table("users")
    op.rename_table("_migration_users", "users")

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("users", "id")
    op.drop_table("scores")
    # ### end Alembic commands ###
