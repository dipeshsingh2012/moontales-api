import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StoryStatus(str, enum.Enum):
    pending = "pending"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class Story(Base):
    """SQLAlchemy ORM model for a generated children's story."""

    __tablename__ = "stories"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # ── Job state ─────────────────────────────────────────────────────────────
    status: Mapped[StoryStatus] = mapped_column(
        Enum(StoryStatus, name="story_status"),
        nullable=False,
        default=StoryStatus.pending,
    )

    # ── Story metadata ────────────────────────────────────────────────────────
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # user_cues: list of strings like ["brave girl", "dragon", "forest"]
    user_cues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # pages: list of StoryPage dicts once generation is complete
    pages: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Error handling ────────────────────────────────────────────────────────
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Soft delete ───────────────────────────────────────────────────────────
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Story id={self.id} status={self.status} user_id={self.user_id!r}>"
