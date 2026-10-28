"""Shot ORM model — one of three storyboard shots in a project."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ShotStatus(str, enum.Enum):
    """Per-shot generation status."""

    PENDING = "PENDING"
    GENERATING = "GENERATING"
    DONE = "DONE"
    FAILED = "FAILED"


class Shot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shots"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    shot_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Creative direction from the planner
    description: Mapped[str] = mapped_column(Text, nullable=False)
    visual_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Narration text for this shot's segment
    narration_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generated asset paths
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generation status
    status: Mapped[ShotStatus] = mapped_column(
        Enum(ShotStatus, name="shot_status", native_enum=False),
        default=ShotStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="shots")

    def __repr__(self) -> str:
        return f"<Shot {self.id} #{self.shot_number} status={self.status.value}>"

