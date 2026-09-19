"""add index for user todo listing and counts

Revision ID: 9d5f3e7a1b2c
Revises: a0790c76a129
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9d5f3e7a1b2c"
down_revision: Union[str, None] = "a0790c76a129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_todos_user_id_created_at",
        "todos",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_todos_user_id_created_at", table_name="todos")