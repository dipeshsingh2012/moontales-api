"""001 — Create stories table

Revision ID: 001
Revises: (none — initial migration)
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create the story_status enum type ─────────────────────────────────────
    story_status_enum = postgresql.ENUM(
        "pending",
        "generating",
        "completed",
        "failed",
        name="story_status",
        create_type=True,
    )
    story_status_enum.create(op.get_bind(), checkfirst=True)

    # ── Create the stories table ───────────────────────────────────────────────
    op.create_table(
        "stories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "generating",
                "completed",
                "failed",
                name="story_status",
                create_type=False,  # already created above
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("user_cues", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("pages", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── Indices ───────────────────────────────────────────────────────────────
    op.create_index("ix_stories_id", "stories", ["id"], unique=False)
    op.create_index("ix_stories_user_id", "stories", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stories_user_id", table_name="stories")
    op.drop_index("ix_stories_id", table_name="stories")
    op.drop_table("stories")

    # Remove the enum type
    sa.Enum(name="story_status").drop(op.get_bind(), checkfirst=True)
