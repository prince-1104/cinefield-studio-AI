"""AI Usage and Model Pricing ORM models for centralized AI cost analytics."""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.shot import Shot
    from app.models.job import Job


class BillingUnit(str, enum.Enum):
    """Supported billing units across AI providers."""

    TOKENS = "tokens"
    VIDEO_SECONDS = "video_seconds"
    VIDEO_MINUTES = "video_minutes"
    AUDIO_SECONDS = "audio_seconds"
    REQUESTS = "requests"


class CostStatus(str, enum.Enum):
    """Cost reconciliation classification."""

    ESTIMATED = "ESTIMATED"
    ACTUAL = "ACTUAL"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"


class RequestStatus(str, enum.Enum):
    """Execution status of an AI API request."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class UsageOrigin(str, enum.Enum):
    """Origin of the recorded usage to distinguish production from test or simulation."""

    PRODUCTION = "production"
    TEST = "test"
    SIMULATION = "simulation"
    UNVERIFIED = "unverified"


class AIModelPricing(UUIDPrimaryKeyMixin, Base):
    """Centralized model pricing configuration versioned by effective dates."""

    __tablename__ = "ai_model_pricing"

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    billing_unit: Mapped[str] = mapped_column(String(32), default=BillingUnit.TOKENS.value, nullable=False)

    # Token-based pricing per million tokens (Claude, Gemini Text, GPT)
    input_price_per_million: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    output_price_per_million: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    cached_input_price_per_million: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Video duration pricing (Seedance, Gemini Video)
    video_price_per_second: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    video_price_per_minute: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_ai_pricing_provider_model", "provider", "model"),
        Index("ix_ai_pricing_effective", "effective_from", "effective_until"),
    )

    def __repr__(self) -> str:
        return f"<AIModelPricing {self.provider}/{self.model} unit={self.billing_unit} currency={self.currency}>"


class AIUsageRecord(UUIDPrimaryKeyMixin, Base):
    """Immutable ledger entry tracking a single AI API call, token/second usage, and cost."""

    __tablename__ = "ai_usage_records"

    # Contextual references
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pricing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_model_pricing.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Contextual relationships
    project: Mapped["Project | None"] = relationship("Project", foreign_keys=[project_id], lazy="selectin")
    shot: Mapped["Shot | None"] = relationship("Shot", foreign_keys=[shot_id], lazy="selectin")
    job: Mapped["Job | None"] = relationship("Job", foreign_keys=[job_id], lazy="selectin")

    # Provider and operation descriptors
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # e.g., creative_brief, storyboard_plan, video_generation, video_retry, tts_narration

    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Measured consumption
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Financial accounting with Decimal precision
    billing_unit: Mapped[str] = mapped_column(String(32), default=BillingUnit.TOKENS.value, nullable=False)
    unit_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"), nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"), nullable=False)
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    # Audit & Status
    usage_origin: Mapped[str] = mapped_column(
        String(32),
        default=UsageOrigin.PRODUCTION.value,
        nullable=False,
        index=True,
    )
    cost_status: Mapped[str] = mapped_column(String(32), default=CostStatus.ESTIMATED.value, nullable=False, index=True)
    request_status: Mapped[str] = mapped_column(String(32), default=RequestStatus.SUCCESS.value, nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_ai_usage_proj_created", "project_id", "created_at"),
        Index("ix_ai_usage_prov_model", "provider", "model", "created_at"),
        Index("ix_ai_usage_origin_created", "usage_origin", "created_at"),
    )

    @property
    def project_name(self) -> str | None:
        return self.project.product_name if self.project else None

    @property
    def shot_number(self) -> int | None:
        return self.shot.shot_number if self.shot else None

    @property
    def shot_description(self) -> str | None:
        return self.shot.description if self.shot else None

    @property
    def visual_prompt(self) -> str | None:
        return self.shot.visual_prompt if self.shot else None

    @property
    def video_path(self) -> str | None:
        if self.shot and self.shot.video_path:
            return self.shot.video_path
        if self.project and self.project.final_video_path:
            return self.project.final_video_path
        return None

    @property
    def has_media(self) -> bool:
        return bool(self.video_path or (self.project and self.project.narration_path))

    def __repr__(self) -> str:
        return (
            f"<AIUsageRecord {self.id} prov={self.provider} op={self.operation} "
            f"est={self.estimated_cost} act={self.actual_cost} status={self.cost_status}>"
        )

