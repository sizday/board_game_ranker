"""add user model and update ratings

Revision ID: 0002_add_user_model_and_update_ratings
Revises: 0001_initial_schema_with_uuid
Create Date: 2026-02-21 22:35:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "0002_add_user_model_and_update_ratings"
down_revision: Union[str, None] = "0001_initial_schema_with_uuid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создание таблицы users
    op.create_table(
        "users",
        sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("telegram_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )

    # Добавление индексов для users
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    # Добавление колонки user_id в таблицу ratings
    op.add_column("ratings", sa.Column("user_id", UUID(), nullable=True))
    op.create_foreign_key(
        "fk_ratings_user_id",
        "ratings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE"
    )

    # Добавление колонки user_id в таблицу ranking_sessions
    op.add_column("ranking_sessions", sa.Column("user_id", UUID(), nullable=True))
    op.create_foreign_key(
        "fk_ranking_sessions_user_id",
        "ranking_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE"
    )

    # Создание индекса для user_id в ratings
    op.create_index("ix_ratings_user_id", "ratings", ["user_id"], unique=False)

    # Создание индекса для user_id в ranking_sessions
    op.create_index("ix_ranking_sessions_user_id", "ranking_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    # Удаление индексов
    op.drop_index("ix_ranking_sessions_user_id", table_name="ranking_sessions")
    op.drop_index("ix_ratings_user_id", table_name="ratings")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_index("ix_users_id", table_name="users")

    # Удаление foreign keys
    op.drop_constraint("fk_ranking_sessions_user_id", "ranking_sessions", type_="foreignkey")
    op.drop_constraint("fk_ratings_user_id", "ratings", type_="foreignkey")

    # Удаление колонок
    op.drop_column("ranking_sessions", "user_id")
    op.drop_column("ratings", "user_id")

    # Удаление таблицы users
    op.drop_table("users")