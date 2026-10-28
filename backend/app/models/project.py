"""Project ORM model — represents an ad-film production."""

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.shot import Shot
    from app.models.timeline_edit import TimelineEdit


class ProjectStage(str, enum.Enum):
    """Stage-gate enum tracking where a project sits in the pipeline."""

    BRIEF = "BRIEF"
    SCRIPT = "SCRIPT"
    STORYBOARD_APPROVED = "STORYBOARD_APPROVED"
    VIDEOS = "VIDEOS"
    NARRATION = "NARRATION"
    RENDERING = "RENDERING"
    ASSEMBLED = "ASSEMBLED"
    FAILED = "FAILED"


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(500), nullable=False)
    tone: Mapped[str] = mapped_column(String(255), nullable=False)
    cta: Mapped[str] = mapped_column(Text, nullable=False)

    # Production specifications
    target_duration: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    shot_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9", nullable=False)

    # Progress tracking
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_stage_label: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # AI-generated script (populated after PLAN_SCRIPT job)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stage-gate for resumable pipeline
    stage: Mapped[ProjectStage] = mapped_column(
        Enum(ProjectStage, name="project_stage", native_enum=False),
        default=ProjectStage.BRIEF,
        nullable=False,
    )

    # File paths for uploaded / generated assets
    product_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    narration_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Measured video metadata from ffprobe (duration, dimensions, fps, bitrate)
    video_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    shots: Mapped[list["Shot"]] = relationship(
        "Shot",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Shot.shot_number",
    )
    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Job.created_at",
    )
    timeline_edits: Mapped[list["TimelineEdit"]] = relationship(
        "TimelineEdit",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TimelineEdit.version.desc()",
    )

    def __repr__(self) -> str:
        return f"<Project {self.id} '{self.product_name}' stage={self.stage.value} shots={self.shot_count}>"
