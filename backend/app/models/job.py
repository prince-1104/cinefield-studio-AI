"""Job ORM model — a unit of work dispatched to the background worker."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobType(str, enum.Enum):
    """Discriminator for what kind of work a job performs."""

    PLAN_SCRIPT = "PLAN_SCRIPT"
    GENERATE_VIDEO = "GENERATE_VIDEO"
    GENERATE_TTS = "GENERATE_TTS"
    ASSEMBLE = "ASSEMBLE"


class JobStatus(str, enum.Enum):
    """Lifecycle states of a background job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type", native_enum=False),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", native_enum=False),
        default=JobStatus.QUEUED,
        nullable=False,
    )

    # Arbitrary input/output data
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job {self.id} type={self.job_type.value} status={self.status.value}>"

