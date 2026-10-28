"""TimelineEdit ORM model — stores versioned, editable timeline compositions."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class TimelineEdit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "timeline_edits"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    timeline_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Path to the exported MP4 rendered specifically from this timeline version
    rendered_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="timeline_edits")

    def __repr__(self) -> str:
        return f"<TimelineEdit project={self.project_id} v={self.version} current={self.is_current}>"

