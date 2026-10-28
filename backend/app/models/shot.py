"""Shot ORM model — represents a single storyboard shot in a project."""

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ShotStatus(str, enum.Enum):
    """Detailed per-shot generation status."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    GENERATING = "GENERATING"
    DOWNLOADING = "DOWNLOADING"
    VALIDATING = "VALIDATING"
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

    # Timeline and duration boundaries
    start_time: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    target_duration: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    actual_duration: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Creative direction from the planner
    description: Mapped[str] = mapped_column(Text, nullable=False)
    visual_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    camera_motion: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transition: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Narration text for this shot's segment
    narration_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # External provider tracking
    provider_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

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
        return f"<Shot {self.id} #{self.shot_number} [{self.start_time}-{self.end_time}s] status={self.status.value}>"
