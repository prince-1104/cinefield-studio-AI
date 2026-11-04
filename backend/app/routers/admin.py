"""Admin analytics and AI cost management router."""

import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.ai_usage import AIModelPricing
from app.schemas.ai_usage import (
    AIModelPricingCreate,
    AIModelPricingResponse,
    AIUsageRecordResponse,
    ModelMetricsResponse,
    OverviewMetricsResponse,
    PaginatedUsageResponse,
    ProjectCostMetricsResponse,
    ProjectDetailMetricsResponse,
    ProviderMetricsResponse,
    ReconciliationRequest,
    ReconciliationResponse,
)
from app.services.ai_usage_service import AIUsageService, seed_default_pricing

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def verify_admin_auth(
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> bool:
    """Verify admin secret key to protect all admin capabilities."""
    provided_key = None
    if x_admin_key:
        provided_key = x_admin_key
    elif authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() in ("bearer", "token", "admin"):
            provided_key = parts[1]
        elif len(parts) == 1:
            provided_key = parts[0]

    expected_key = settings.ADMIN_API_KEY
    if not provided_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication failed: invalid or missing admin key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return True


def parse_date_range(
    range_preset: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Parse date filter presets or explicit ISO strings into UTC datetimes."""
    now = datetime.now(timezone.utc)
    if range_preset:
        preset = range_preset.lower()
        if preset == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, now
        elif preset in ("7d", "7_days", "last_7_days"):
            return now - timedelta(days=7), now
        elif preset in ("30d", "30_days", "last_30_days"):
            return now - timedelta(days=30), now
        elif preset in ("month", "this_month"):
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, now

    s_dt = datetime.fromisoformat(start_date).astimezone(timezone.utc) if start_date else None
    e_dt = datetime.fromisoformat(end_date).astimezone(timezone.utc) if end_date else None
    return s_dt, e_dt


@router.get("/metrics/overview", response_model=OverviewMetricsResponse)
async def get_overview_metrics(
    range_preset: str | None = Query(default=None, alias="range"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    origin: str = Query(default="production", description="Filter by usage origin: production, test, simulation, or all"),
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> OverviewMetricsResponse:
    """Retrieve high-level spend, token consumption, and video generation metrics."""
    s_dt, e_dt = parse_date_range(range_preset, start_date, end_date)
    await seed_default_pricing(session)
    data = await AIUsageService.get_overview_metrics(session, s_dt, e_dt, origin=origin)
    return OverviewMetricsResponse(**data)


@router.get("/metrics/providers", response_model=list[ProviderMetricsResponse])
async def get_provider_metrics(
    range_preset: str | None = Query(default=None, alias="range"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    origin: str = Query(default="production", description="Filter by usage origin: production, test, simulation, or all"),
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> list[ProviderMetricsResponse]:
    """Breakdown of usage and failure rate by AI provider."""
    s_dt, e_dt = parse_date_range(range_preset, start_date, end_date)
    data = await AIUsageService.get_provider_metrics(session, s_dt, e_dt, origin=origin)
    return [ProviderMetricsResponse(**d) for d in data]


@router.get("/metrics/models", response_model=list[ModelMetricsResponse])
async def get_model_metrics(
    range_preset: str | None = Query(default=None, alias="range"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    origin: str = Query(default="production", description="Filter by usage origin: production, test, simulation, or all"),
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> list[ModelMetricsResponse]:
    """Breakdown of requests, spend, and failure rate by exact model identifier."""
    s_dt, e_dt = parse_date_range(range_preset, start_date, end_date)
    data = await AIUsageService.get_model_metrics(session, s_dt, e_dt, origin=origin)
    return [ModelMetricsResponse(**d) for d in data]


@router.get("/metrics/projects", response_model=list[ProjectCostMetricsResponse])
async def get_projects_cost_metrics(
    range_preset: str | None = Query(default=None, alias="range"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    origin: str = Query(default="production", description="Filter by usage origin: production, test, simulation, or all"),
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectCostMetricsResponse]:
    """Project-level cost ledger comparing spend across projects."""
    s_dt, e_dt = parse_date_range(range_preset, start_date, end_date)
    data = await AIUsageService.get_projects_cost_metrics(session, s_dt, e_dt, origin=origin)
    return [ProjectCostMetricsResponse(**d) for d in data]


@router.get("/metrics/projects/{project_id}", response_model=ProjectDetailMetricsResponse)
async def get_project_detail_metrics(
    project_id: uuid.UUID,
    origin: str = Query(default="production", description="Filter by usage origin: production, test, simulation, or all"),
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> ProjectDetailMetricsResponse:
    """Detailed AI cost analytics for a single project (cost per shot, per video, retries)."""
    data = await AIUsageService.get_project_detail_metrics(session, project_id, origin=origin)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )
    return ProjectDetailMetricsResponse(**data)


@router.get("/usage", response_model=PaginatedUsageResponse)
async def get_usage_ledger(
    project_id: uuid.UUID | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    operation: str | None = Query(default=None),
    request_status: str | None = Query(default=None),
    cost_status: str | None = Query(default=None),
    origin: str = Query(default="production", description="Filter by usage origin: production, test, simulation, or all"),
    range_preset: str | None = Query(default=None, alias="range"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> PaginatedUsageResponse:
    """Paginated and searchable individual AI API usage ledger."""
    s_dt, e_dt = parse_date_range(range_preset, start_date, end_date)
    items, total = await AIUsageService.get_usage_ledger(
        session=session,
        project_id=project_id,
        provider=provider,
        model=model,
        operation=operation,
        request_status=request_status,
        cost_status=cost_status,
        origin=origin,
        start_date=s_dt,
        end_date=e_dt,
        limit=limit,
        offset=offset,
    )
    return PaginatedUsageResponse(
        items=[AIUsageRecordResponse.model_validate(it) for it in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/usage/export-csv")
async def export_usage_csv(
    project_id: uuid.UUID | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    origin: str = Query(default="production", description="Filter by usage origin: production, test, simulation, or all"),
    range_preset: str | None = Query(default=None, alias="range"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Export filtered AI usage records to CSV."""
    s_dt, e_dt = parse_date_range(range_preset, start_date, end_date)
    csv_data = await AIUsageService.export_usage_csv(
        session=session,
        project_id=project_id,
        provider=provider,
        model=model,
        origin=origin,
        start_date=s_dt,
        end_date=e_dt,
    )
    filename = f"pexyl_ai_usage_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@router.get("/pricing", response_model=list[AIModelPricingResponse])
async def list_model_pricing(
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> list[AIModelPricingResponse]:
    """Retrieve all model pricing rules."""
    await seed_default_pricing(session)
    stmt = select(AIModelPricing).order_by(AIModelPricing.provider, AIModelPricing.model, AIModelPricing.effective_from.desc())
    records = (await session.execute(stmt)).scalars().all()
    return [AIModelPricingResponse.model_validate(r) for r in records]


@router.post("/pricing", response_model=AIModelPricingResponse)
async def create_or_update_model_pricing(
    payload: AIModelPricingCreate,
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> AIModelPricingResponse:
    """Create a new version of model pricing without overwriting historical records."""
    now = datetime.now(timezone.utc)

    # Expire previous active pricing for this provider/model
    stmt = (
        select(AIModelPricing)
        .where(
            AIModelPricing.provider == payload.provider,
            AIModelPricing.model == payload.model,
            AIModelPricing.effective_until.is_(None),
        )
    )
    active = (await session.execute(stmt)).scalars().all()
    for item in active:
        item.effective_until = now

    new_pricing = AIModelPricing(
        provider=payload.provider,
        model=payload.model,
        billing_unit=payload.billing_unit,
        input_price_per_million=payload.input_price_per_million,
        output_price_per_million=payload.output_price_per_million,
        cached_input_price_per_million=payload.cached_input_price_per_million,
        video_price_per_second=payload.video_price_per_second,
        video_price_per_minute=payload.video_price_per_minute,
        effective_from=now,
        currency=payload.currency,
    )
    session.add(new_pricing)
    await session.commit()
    await session.refresh(new_pricing)
    return AIModelPricingResponse.model_validate(new_pricing)


@router.post("/reconcile", response_model=ReconciliationResponse)
async def reconcile_usage_record(
    payload: ReconciliationRequest,
    _: bool = Depends(verify_admin_auth),
    session: AsyncSession = Depends(get_session),
) -> ReconciliationResponse:
    """Reconcile estimated cost with actual provider charge using task ID."""
    success = await AIUsageService.reconcile_task_billing(
        session=session,
        provider_task_id=payload.provider_task_id,
        actual_cost=payload.actual_cost,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usage record with provider task ID '{payload.provider_task_id}' not found",
        )
    await session.commit()
    return ReconciliationResponse(
        success=True,
        provider_task_id=payload.provider_task_id,
        actual_cost=payload.actual_cost,
        message="Record successfully reconciled with actual provider cost",
    )

