"""Pydantic schemas for AI Usage Analytics, Ledger, and Pricing APIs."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AIModelPricingResponse(BaseModel):
    id: uuid.UUID
    provider: str
    model: str
    billing_unit: str
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None
    cached_input_price_per_million: float | None = None
    video_price_per_second: float | None = None
    video_price_per_minute: float | None = None
    effective_from: datetime
    effective_until: datetime | None = None
    currency: str = "USD"
    created_at: datetime

    model_config = {"from_attributes": True}


class AIModelPricingCreate(BaseModel):
    provider: str
    model: str
    billing_unit: str = "tokens"
    input_price_per_million: Decimal | None = None
    output_price_per_million: Decimal | None = None
    cached_input_price_per_million: Decimal | None = None
    video_price_per_second: Decimal | None = None
    video_price_per_minute: Decimal | None = None
    currency: str = "USD"


class AIUsageRecordResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None = None
    shot_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    provider: str
    model: str
    operation: str
    provider_request_id: str | None = None
    provider_task_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    video_duration_seconds: float | None = None
    billing_unit: str
    unit_quantity: float
    unit_price: float
    estimated_cost: float
    actual_cost: float | None = None
    currency: str = "USD"
    usage_origin: str = "production"
    cost_status: str
    request_status: str
    error_code: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    # Contextual enriched fields
    project_name: str | None = None
    shot_number: int | None = None
    shot_description: str | None = None
    visual_prompt: str | None = None
    video_path: str | None = None
    has_media: bool = False

    model_config = {"from_attributes": True}


class AIUsageRecordDetailResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None = None
    shot_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    provider: str
    model: str
    operation: str
    provider_request_id: str | None = None
    provider_task_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    video_duration_seconds: float | None = None
    billing_unit: str
    unit_quantity: float
    unit_price: float
    estimated_cost: float
    actual_cost: float | None = None
    currency: str = "USD"
    usage_origin: str = "production"
    cost_status: str
    request_status: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    # Enriched context & content
    project: dict[str, Any] | None = None
    shot: dict[str, Any] | None = None
    job: dict[str, Any] | None = None
    media_url: str | None = None
    media_type: str | None = None  # "video", "audio", "image", None
    content_title: str | None = None
    content_prompt: str | None = None
    content_output: str | None = None

    model_config = {"from_attributes": True}


class OverviewMetricsResponse(BaseModel):
    total_spend: float
    actual_spend: float
    estimated_spend: float
    unknown_spend: float
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_video_generations: int
    successful_generations: int
    failed_generations: int
    total_video_seconds: float
    total_projects_using_ai: int


class ProviderMetricsResponse(BaseModel):
    provider: str
    request_count: int
    total_cost: float
    input_tokens: int
    output_tokens: int
    video_generation_count: int
    failure_rate: float


class ModelMetricsResponse(BaseModel):
    provider: str
    model: str
    total_requests: int
    actual_cost: float
    estimated_cost: float
    total_cost: float
    avg_cost_per_request: float
    input_tokens: int
    output_tokens: int
    video_generation_count: int
    failure_rate: float


class ProjectCostMetricsResponse(BaseModel):
    project_id: str
    project_name: str
    owner: str = "Workspace Admin"
    total_requests: int
    claude_model: str
    claude_input_tokens: int
    claude_output_tokens: int
    seedance_model: str
    video_generation_count: int
    successful_videos: int
    failed_videos: int
    actual_spend: float
    estimated_spend: float
    total_spend: float


class ProjectDetailMetricsResponse(BaseModel):
    project_id: str
    project_name: str
    total_spend: float
    claude_spend: float
    seedance_spend: float
    retry_spend: float
    failed_spend: float
    cost_per_video: float
    cost_per_shot: float
    claude_tokens: dict[str, int]
    video_generations_count: int
    shot_costs: dict[str, float]
    records_count: int


class PaginatedUsageResponse(BaseModel):
    items: list[AIUsageRecordResponse]
    total: int
    limit: int
    offset: int


class ReconciliationRequest(BaseModel):
    provider_task_id: str
    actual_cost: Decimal = Field(..., gt=0)


class ReconciliationResponse(BaseModel):
    success: bool
    provider_task_id: str
    actual_cost: float
    message: str

