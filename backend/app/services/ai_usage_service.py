"""Centralized AI usage tracking, Decimal cost calculation, and analytics service."""

import csv
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_usage import AIModelPricing, AIUsageRecord, BillingUnit, CostStatus, RequestStatus, UsageOrigin
from app.models.project import Project

logger = logging.getLogger(__name__)

# Standard financial decimal quantizer (4 decimal places for display, 6 for storage)
SIX_PLACES = Decimal("0.000001")
FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")


DEFAULT_PRICING_SEEDS = [
    {
        "provider": "claude",
        "model": "claude-3-7-sonnet-20250219",
        "billing_unit": BillingUnit.TOKENS.value,
        "input_price_per_million": Decimal("3.000000"),
        "output_price_per_million": Decimal("15.000000"),
        "cached_input_price_per_million": Decimal("0.300000"),
    },
    {
        "provider": "claude",
        "model": "claude-3-5-sonnet-20241022",
        "billing_unit": BillingUnit.TOKENS.value,
        "input_price_per_million": Decimal("3.000000"),
        "output_price_per_million": Decimal("15.000000"),
        "cached_input_price_per_million": Decimal("0.300000"),
    },
    {
        "provider": "claude",
        "model": "claude-3-5-haiku-20241022",
        "billing_unit": BillingUnit.TOKENS.value,
        "input_price_per_million": Decimal("0.800000"),
        "output_price_per_million": Decimal("4.000000"),
        "cached_input_price_per_million": Decimal("0.080000"),
    },
    {
        "provider": "seedance",
        "model": "dreamina-seedance-2-5-260628",
        "billing_unit": BillingUnit.VIDEO_SECONDS.value,
        "video_price_per_second": Decimal("0.050000"),
        "video_price_per_minute": Decimal("3.000000"),
    },
    {
        "provider": "seedance",
        "model": "seedance-1-0-pro-250528",
        "billing_unit": BillingUnit.VIDEO_SECONDS.value,
        "video_price_per_second": Decimal("0.035000"),
        "video_price_per_minute": Decimal("2.100000"),
    },
    {
        "provider": "gemini",
        "model": "gemini-omni-1.1-flash",
        "billing_unit": BillingUnit.VIDEO_SECONDS.value,
        "video_price_per_second": Decimal("0.020000"),
        "video_price_per_minute": Decimal("1.200000"),
    },
    {
        "provider": "gemini",
        "model": "gemini-3.8-flash",
        "billing_unit": BillingUnit.TOKENS.value,
        "input_price_per_million": Decimal("0.075000"),
        "output_price_per_million": Decimal("0.300000"),
    },
    {
        "provider": "openai",
        "model": "gpt-4o-mini-tts",
        "billing_unit": BillingUnit.TOKENS.value,
        "input_price_per_million": Decimal("0.150000"),
        "output_price_per_million": Decimal("0.600000"),
    },
]


async def seed_default_pricing(session: AsyncSession) -> None:
    """Seed baseline AI model pricing if table is empty or missing standard models."""
    for item in DEFAULT_PRICING_SEEDS:
        stmt = (
            select(AIModelPricing)
            .where(
                AIModelPricing.provider == item["provider"],
                AIModelPricing.model == item["model"],
                AIModelPricing.effective_until.is_(None),
            )
            .limit(1)
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if not existing:
            pricing = AIModelPricing(
                provider=item["provider"],
                model=item["model"],
                billing_unit=item["billing_unit"],
                input_price_per_million=item.get("input_price_per_million"),
                output_price_per_million=item.get("output_price_per_million"),
                cached_input_price_per_million=item.get("cached_input_price_per_million"),
                video_price_per_second=item.get("video_price_per_second"),
                video_price_per_minute=item.get("video_price_per_minute"),
                effective_from=datetime.now(timezone.utc),
                currency="USD",
            )
            session.add(pricing)
    await session.commit()


async def get_effective_pricing(
    session: AsyncSession,
    provider: str,
    model: str,
    timestamp: datetime | None = None,
) -> AIModelPricing | None:
    """Retrieve pricing effective for a specific provider and model at a given time."""
    t = timestamp or datetime.now(timezone.utc)
    stmt = (
        select(AIModelPricing)
        .where(
            AIModelPricing.provider == provider,
            AIModelPricing.model == model,
            AIModelPricing.effective_from <= t,
            or_(
                AIModelPricing.effective_until.is_(None),
                AIModelPricing.effective_until > t,
            ),
        )
        .order_by(AIModelPricing.effective_from.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    pricing = result.scalar_one_or_none()

    # Fallback to provider default if exact model string isn't matched
    if not pricing:
        fallback_stmt = (
            select(AIModelPricing)
            .where(
                AIModelPricing.provider == provider,
                AIModelPricing.effective_from <= t,
                or_(
                    AIModelPricing.effective_until.is_(None),
                    AIModelPricing.effective_until > t,
                ),
            )
            .order_by(AIModelPricing.effective_from.desc())
            .limit(1)
        )
        pricing = (await session.execute(fallback_stmt)).scalar_one_or_none()

    return pricing


def calculate_token_cost(
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int | None,
    pricing: AIModelPricing | None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Calculate token cost using exact Decimal arithmetic.

    Returns:
        (total_cost, input_cost, output_cost)
    """
    if not pricing:
        return Decimal("0"), Decimal("0"), Decimal("0")

    in_price = pricing.input_price_per_million or Decimal("0")
    out_price = pricing.output_price_per_million or Decimal("0")
    cached_price = pricing.cached_input_price_per_million or (in_price * Decimal("0.10"))

    one_million = Decimal("1000000")

    # Regular input tokens (subtract cached if separated)
    cached_count = Decimal(cached_tokens or 0)
    in_count = max(Decimal(0), Decimal(input_tokens) - cached_count)
    out_count = Decimal(output_tokens)

    in_cost = (in_count * in_price / one_million).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)
    cached_cost = (cached_count * cached_price / one_million).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)
    out_cost = (out_count * out_price / one_million).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)

    total = (in_cost + cached_cost + out_cost).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)
    return total, (in_cost + cached_cost), out_cost


def calculate_video_cost(
    duration_seconds: float | Decimal,
    pricing: AIModelPricing | None,
) -> Decimal:
    """Calculate video cost per duration second with Decimal precision."""
    if not pricing or not pricing.video_price_per_second:
        # Default fallback to $0.05/sec for Seedance if unconfigured
        price_per_sec = Decimal("0.050000")
    else:
        price_per_sec = pricing.video_price_per_second

    dur = Decimal(str(duration_seconds))
    cost = (dur * price_per_sec).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)
    return cost


class AIUsageService:
    """Centralized management of AI usage ledger and cost analytics."""

    @staticmethod
    async def record_claude_usage(
        session: AsyncSession,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int | None = None,
        provider_request_id: str | None = None,
        project_id: uuid.UUID | None = None,
        shot_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        request_status: str = RequestStatus.SUCCESS.value,
        error_code: str | None = None,
        error_message: str | None = None,
        usage_origin: str = UsageOrigin.PRODUCTION.value,
    ) -> AIUsageRecord:
        """Record Claude API usage and compute token-based cost with idempotency protection."""
        # Automatically isolate test runs to prevent test pollution of production analytics
        if usage_origin == UsageOrigin.PRODUCTION.value and "PYTEST_CURRENT_TEST" in os.environ:
            usage_origin = UsageOrigin.TEST.value

        # Idempotency check: prevent duplicate insertion for the exact same provider_request_id
        if provider_request_id:
            existing = (
                await session.execute(
                    select(AIUsageRecord).where(AIUsageRecord.provider_request_id == provider_request_id).limit(1)
                )
            ).scalar_one_or_none()
            if existing:
                existing.input_tokens = input_tokens
                existing.output_tokens = output_tokens
                existing.request_status = request_status
                if error_code:
                    existing.error_code = error_code
                if error_message:
                    existing.error_message = error_message
                await session.flush()
                return existing

        pricing = await get_effective_pricing(session, "claude", model)
        total_cost, _, _ = calculate_token_cost(input_tokens, output_tokens, cached_tokens, pricing)

        total_tokens = input_tokens + output_tokens
        unit_price = pricing.input_price_per_million if pricing else Decimal("3.00")

        record = AIUsageRecord(
            project_id=project_id,
            shot_id=shot_id,
            job_id=job_id,
            pricing_id=pricing.id if pricing else None,
            provider="claude",
            model=model,
            operation=operation,
            provider_request_id=provider_request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_tokens,
            billing_unit=BillingUnit.TOKENS.value,
            unit_quantity=Decimal(total_tokens),
            unit_price=unit_price,
            estimated_cost=total_cost,
            actual_cost=total_cost,  # Claude tokens are exact provider measurements
            currency="USD",
            usage_origin=usage_origin,
            cost_status=CostStatus.ACTUAL.value if total_tokens > 0 else CostStatus.ESTIMATED.value,
            request_status=request_status,
            error_code=error_code,
            error_message=error_message,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def record_seedance_usage(
        session: AsyncSession,
        model: str,
        operation: str,
        duration_seconds: float | Decimal,
        provider_task_id: str | None = None,
        provider_request_id: str | None = None,
        project_id: uuid.UUID | None = None,
        shot_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        actual_provider_cost: Decimal | None = None,
        request_status: str = RequestStatus.SUCCESS.value,
        error_code: str | None = None,
        error_message: str | None = None,
        usage_origin: str = UsageOrigin.PRODUCTION.value,
    ) -> AIUsageRecord:
        """Record Seedance video generation usage and compute duration-based cost with idempotency protection."""
        # Automatically isolate test runs to prevent test pollution of production analytics
        if usage_origin == UsageOrigin.PRODUCTION.value and "PYTEST_CURRENT_TEST" in os.environ:
            usage_origin = UsageOrigin.TEST.value

        # Idempotency check: prevent duplicate insertion for the exact same provider_task_id
        if provider_task_id:
            existing = (
                await session.execute(
                    select(AIUsageRecord).where(
                        AIUsageRecord.provider_task_id == provider_task_id,
                        AIUsageRecord.operation == operation,
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if existing:
                existing.request_status = request_status
                if actual_provider_cost is not None:
                    existing.actual_cost = actual_provider_cost
                    existing.cost_status = CostStatus.ACTUAL.value
                if error_code:
                    existing.error_code = error_code
                if error_message:
                    existing.error_message = error_message
                await session.flush()
                return existing

        pricing = await get_effective_pricing(session, "seedance", model)
        dur_dec = Decimal(str(duration_seconds))
        estimated_cost = calculate_video_cost(dur_dec, pricing)

        unit_price = pricing.video_price_per_second if (pricing and pricing.video_price_per_second) else Decimal("0.050")
        cost_status = CostStatus.ACTUAL.value if actual_provider_cost is not None else CostStatus.ESTIMATED.value

        record = AIUsageRecord(
            project_id=project_id,
            shot_id=shot_id,
            job_id=job_id,
            pricing_id=pricing.id if pricing else None,
            provider="seedance",
            model=model,
            operation=operation,
            provider_request_id=provider_request_id,
            provider_task_id=provider_task_id,
            video_duration_seconds=dur_dec,
            billing_unit=BillingUnit.VIDEO_SECONDS.value,
            unit_quantity=dur_dec,
            unit_price=unit_price,
            estimated_cost=estimated_cost,
            actual_cost=actual_provider_cost,
            currency="USD",
            usage_origin=usage_origin,
            cost_status=cost_status,
            request_status=request_status,
            error_code=error_code,
            error_message=error_message,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc) if request_status == RequestStatus.SUCCESS.value else None,
        )
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def reconcile_task_billing(
        session: AsyncSession,
        provider_task_id: str,
        actual_cost: Decimal,
    ) -> bool:
        """Reconcile an existing usage record with actual provider billing data."""
        stmt = (
            select(AIUsageRecord)
            .where(AIUsageRecord.provider_task_id == provider_task_id)
            .order_by(desc(AIUsageRecord.created_at))
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        if not records:
            return False

        for record in records:
            record.actual_cost = actual_cost
            record.cost_status = CostStatus.RECONCILED.value
            record.completed_at = datetime.now(timezone.utc)
        await session.flush()
        return True

    # -------------------------------------------------------------------------
    # Analytics & Aggregation Queries for Admin Dashboard
    # -------------------------------------------------------------------------

    @staticmethod
    def _apply_date_filter(query: Any, column: Any, start_date: datetime | None, end_date: datetime | None) -> Any:
        if start_date:
            query = query.where(column >= start_date)
        if end_date:
            query = query.where(column <= end_date)
        return query

    @classmethod
    def _apply_filters(
        cls,
        query: Any,
        column: Any,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        origin: str | None = UsageOrigin.PRODUCTION.value,
        usage_model: Any = AIUsageRecord,
    ) -> Any:
        query = cls._apply_date_filter(query, column, start_date, end_date)
        if origin and origin.lower() != "all":
            query = query.where(usage_model.usage_origin == origin.lower())
        return query

    @classmethod
    async def get_overview_metrics(
        cls,
        session: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        origin: str | None = UsageOrigin.PRODUCTION.value,
    ) -> dict[str, Any]:
        """Compute top-level summary metrics across all AI operations."""
        query = select(
            func.coalesce(func.sum(AIUsageRecord.estimated_cost), 0).label("total_estimated"),
            func.coalesce(func.sum(AIUsageRecord.actual_cost), 0).label("total_actual"),
            func.coalesce(func.sum(AIUsageRecord.input_tokens), 0).label("total_in_tokens"),
            func.coalesce(func.sum(AIUsageRecord.output_tokens), 0).label("total_out_tokens"),
            func.count(AIUsageRecord.id).label("total_requests"),
        )
        query = cls._apply_filters(query, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        res = (await session.execute(query)).one()

        # Video generation stats
        video_q = select(
            func.count(AIUsageRecord.id).label("total_videos"),
            func.count().filter(AIUsageRecord.request_status == RequestStatus.SUCCESS.value).label("successful_videos"),
            func.count().filter(AIUsageRecord.request_status == RequestStatus.FAILED.value).label("failed_videos"),
            func.coalesce(func.sum(AIUsageRecord.video_duration_seconds), 0).label("total_video_seconds"),
        ).where(AIUsageRecord.billing_unit == BillingUnit.VIDEO_SECONDS.value)
        video_q = cls._apply_filters(video_q, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        v_res = (await session.execute(video_q)).one()

        # Distinct AI-using projects
        proj_q = select(func.count(func.distinct(AIUsageRecord.project_id)))
        proj_q = cls._apply_filters(proj_q, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        total_projects = (await session.execute(proj_q)).scalar() or 0

        # Cost status breakdowns
        unknown_q = select(func.coalesce(func.sum(AIUsageRecord.estimated_cost), 0)).where(
            AIUsageRecord.cost_status == CostStatus.UNKNOWN.value
        )
        unknown_q = cls._apply_filters(unknown_q, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        unknown_spend = (await session.execute(unknown_q)).scalar() or Decimal("0")

        total_est = Decimal(str(res.total_estimated))
        total_act = Decimal(str(res.total_actual))

        # Reconciled total spend: use actual when available, otherwise estimated
        reconciled_q = select(
            func.coalesce(
                func.sum(
                    func.coalesce(AIUsageRecord.actual_cost, AIUsageRecord.estimated_cost)
                ),
                0,
            )
        )
        reconciled_q = cls._apply_filters(reconciled_q, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        total_spend = Decimal(str((await session.execute(reconciled_q)).scalar() or "0"))

        return {
            "total_spend": float(total_spend.quantize(FOUR_PLACES)),
            "actual_spend": float(total_act.quantize(FOUR_PLACES)),
            "estimated_spend": float(total_est.quantize(FOUR_PLACES)),
            "unknown_spend": float(unknown_spend.quantize(FOUR_PLACES)),
            "total_requests": int(res.total_requests),
            "total_input_tokens": int(res.total_in_tokens),
            "total_output_tokens": int(res.total_out_tokens),
            "total_tokens": int(res.total_in_tokens + res.total_out_tokens),
            "total_video_generations": int(v_res.total_videos),
            "successful_generations": int(v_res.successful_videos),
            "failed_generations": int(v_res.failed_videos),
            "total_video_seconds": float(v_res.total_video_seconds),
            "total_projects_using_ai": int(total_projects),
        }

    @classmethod
    async def get_provider_metrics(
        cls,
        session: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        origin: str | None = UsageOrigin.PRODUCTION.value,
    ) -> list[dict[str, Any]]:
        """Usage aggregated by AI provider (Claude, Seedance, Gemini, OpenAI)."""
        query = (
            select(
                AIUsageRecord.provider,
                func.count(AIUsageRecord.id).label("request_count"),
                func.coalesce(
                    func.sum(
                        func.coalesce(AIUsageRecord.actual_cost, AIUsageRecord.estimated_cost)
                    ),
                    0,
                ).label("total_cost"),
                func.coalesce(func.sum(AIUsageRecord.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(AIUsageRecord.output_tokens), 0).label("output_tokens"),
                func.count().filter(AIUsageRecord.billing_unit == BillingUnit.VIDEO_SECONDS.value).label("video_count"),
                func.count().filter(AIUsageRecord.request_status == RequestStatus.FAILED.value).label("failed_count"),
            )
            .group_by(AIUsageRecord.provider)
            .order_by(desc("total_cost"))
        )
        query = cls._apply_filters(query, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        rows = (await session.execute(query)).all()

        results = []
        for r in rows:
            req_count = r.request_count or 0
            failed_count = r.failed_count or 0
            failure_rate = (failed_count / req_count * 100) if req_count > 0 else 0.0
            results.append({
                "provider": r.provider,
                "request_count": req_count,
                "total_cost": float(Decimal(str(r.total_cost)).quantize(FOUR_PLACES)),
                "input_tokens": int(r.input_tokens or 0),
                "output_tokens": int(r.output_tokens or 0),
                "video_generation_count": int(r.video_count or 0),
                "failure_rate": round(failure_rate, 2),
            })
        return results

    @classmethod
    async def get_model_metrics(
        cls,
        session: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        origin: str | None = UsageOrigin.PRODUCTION.value,
    ) -> list[dict[str, Any]]:
        """Usage aggregated by exact model identifier."""
        query = (
            select(
                AIUsageRecord.provider,
                AIUsageRecord.model,
                func.count(AIUsageRecord.id).label("request_count"),
                func.coalesce(func.sum(AIUsageRecord.actual_cost), 0).label("actual_cost"),
                func.coalesce(func.sum(AIUsageRecord.estimated_cost), 0).label("estimated_cost"),
                func.coalesce(
                    func.sum(
                        func.coalesce(AIUsageRecord.actual_cost, AIUsageRecord.estimated_cost)
                    ),
                    0,
                ).label("total_cost"),
                func.coalesce(func.sum(AIUsageRecord.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(AIUsageRecord.output_tokens), 0).label("output_tokens"),
                func.count().filter(AIUsageRecord.billing_unit == BillingUnit.VIDEO_SECONDS.value).label("video_count"),
                func.count().filter(AIUsageRecord.request_status == RequestStatus.FAILED.value).label("failed_count"),
            )
            .group_by(AIUsageRecord.provider, AIUsageRecord.model)
            .order_by(desc("total_cost"))
        )
        query = cls._apply_filters(query, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        rows = (await session.execute(query)).all()

        results = []
        for r in rows:
            req_count = r.request_count or 0
            total_cost_dec = Decimal(str(r.total_cost))
            avg_cost = (total_cost_dec / req_count) if req_count > 0 else Decimal("0")
            fail_rate = ((r.failed_count or 0) / req_count * 100) if req_count > 0 else 0.0

            results.append({
                "provider": r.provider,
                "model": r.model,
                "total_requests": req_count,
                "actual_cost": float(Decimal(str(r.actual_cost)).quantize(FOUR_PLACES)),
                "estimated_cost": float(Decimal(str(r.estimated_cost)).quantize(FOUR_PLACES)),
                "total_cost": float(total_cost_dec.quantize(FOUR_PLACES)),
                "avg_cost_per_request": float(avg_cost.quantize(FOUR_PLACES)),
                "input_tokens": int(r.input_tokens or 0),
                "output_tokens": int(r.output_tokens or 0),
                "video_generation_count": int(r.video_count or 0),
                "failure_rate": round(fail_rate, 2),
            })
        return results

    @classmethod
    async def get_projects_cost_metrics(
        cls,
        session: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        origin: str | None = UsageOrigin.PRODUCTION.value,
    ) -> list[dict[str, Any]]:
        """Project-level AI cost table with model breakdown and token metrics."""
        query = (
            select(
                Project.id.label("project_id"),
                Project.product_name,
                func.count(AIUsageRecord.id).label("total_requests"),
                func.coalesce(
                    func.sum(
                        func.coalesce(AIUsageRecord.actual_cost, AIUsageRecord.estimated_cost)
                    ),
                    0,
                ).label("total_spend"),
                func.coalesce(func.sum(AIUsageRecord.actual_cost), 0).label("actual_spend"),
                func.coalesce(func.sum(AIUsageRecord.estimated_cost), 0).label("estimated_spend"),
                func.coalesce(
                    func.sum(AIUsageRecord.input_tokens).filter(AIUsageRecord.provider == "claude"), 0
                ).label("claude_input_tokens"),
                func.coalesce(
                    func.sum(AIUsageRecord.output_tokens).filter(AIUsageRecord.provider == "claude"), 0
                ).label("claude_output_tokens"),
                func.count().filter(AIUsageRecord.provider == "seedance").label("video_generations"),
                func.count().filter(
                    and_(
                        AIUsageRecord.provider == "seedance",
                        AIUsageRecord.request_status == RequestStatus.SUCCESS.value,
                    )
                ).label("successful_videos"),
                func.count().filter(
                    and_(
                        AIUsageRecord.provider == "seedance",
                        AIUsageRecord.request_status == RequestStatus.FAILED.value,
                    )
                ).label("failed_videos"),
            )
            .join(AIUsageRecord, AIUsageRecord.project_id == Project.id)
            .group_by(Project.id, Project.product_name)
            .order_by(desc("total_spend"))
        )
        query = cls._apply_filters(query, AIUsageRecord.created_at, start_date, end_date, origin=origin)
        rows = (await session.execute(query)).all()

        results = []
        for r in rows:
            results.append({
                "project_id": str(r.project_id),
                "project_name": r.product_name,
                "owner": "Workspace Admin",
                "total_requests": int(r.total_requests),
                "claude_model": "claude-3-7-sonnet",
                "claude_input_tokens": int(r.claude_input_tokens),
                "claude_output_tokens": int(r.claude_output_tokens),
                "seedance_model": "seedance-2.5",
                "video_generation_count": int(r.video_generations),
                "successful_videos": int(r.successful_videos),
                "failed_videos": int(r.failed_videos),
                "actual_spend": float(Decimal(str(r.actual_spend)).quantize(FOUR_PLACES)),
                "estimated_spend": float(Decimal(str(r.estimated_spend)).quantize(FOUR_PLACES)),
                "total_spend": float(Decimal(str(r.total_spend)).quantize(FOUR_PLACES)),
            })
        return results

    @classmethod
    async def get_project_detail_metrics(
        cls,
        session: AsyncSession,
        project_id: uuid.UUID,
        origin: str | None = UsageOrigin.PRODUCTION.value,
    ) -> dict[str, Any]:
        """Comprehensive AI usage breakdown for a single project."""
        # Project metadata
        proj = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if not proj:
            return {}

        # Usage records for project
        records_stmt = (
            select(AIUsageRecord)
            .where(AIUsageRecord.project_id == project_id)
        )
        if origin and origin.lower() != "all":
            records_stmt = records_stmt.where(AIUsageRecord.usage_origin == origin.lower())
        records_stmt = records_stmt.order_by(desc(AIUsageRecord.created_at))
        records = (await session.execute(records_stmt)).scalars().all()

        total_spend = Decimal("0")
        claude_spend = Decimal("0")
        seedance_spend = Decimal("0")
        retry_spend = Decimal("0")
        failed_spend = Decimal("0")

        total_in_tokens = 0
        total_out_tokens = 0
        video_count = 0
        shot_costs: dict[str, Decimal] = {}

        for r in records:
            cost = r.actual_cost if r.actual_cost is not None else r.estimated_cost
            cost_dec = Decimal(str(cost or "0"))
            total_spend += cost_dec

            if r.provider == "claude":
                claude_spend += cost_dec
                total_in_tokens += r.input_tokens or 0
                total_out_tokens += r.output_tokens or 0
            elif r.provider == "seedance":
                seedance_spend += cost_dec
                video_count += 1

            if "retry" in r.operation:
                retry_spend += cost_dec
            if r.request_status == RequestStatus.FAILED.value:
                failed_spend += cost_dec

            if r.shot_id:
                shot_key = str(r.shot_id)
                shot_costs[shot_key] = shot_costs.get(shot_key, Decimal("0")) + cost_dec

        cost_per_video = (seedance_spend / video_count) if video_count > 0 else Decimal("0")
        cost_per_shot = (total_spend / len(shot_costs)) if shot_costs else Decimal("0")

        return {
            "project_id": str(proj.id),
            "project_name": proj.product_name,
            "total_spend": float(total_spend.quantize(FOUR_PLACES)),
            "claude_spend": float(claude_spend.quantize(FOUR_PLACES)),
            "seedance_spend": float(seedance_spend.quantize(FOUR_PLACES)),
            "retry_spend": float(retry_spend.quantize(FOUR_PLACES)),
            "failed_spend": float(failed_spend.quantize(FOUR_PLACES)),
            "cost_per_video": float(cost_per_video.quantize(FOUR_PLACES)),
            "cost_per_shot": float(cost_per_shot.quantize(FOUR_PLACES)),
            "claude_tokens": {
                "input": total_in_tokens,
                "output": total_out_tokens,
                "total": total_in_tokens + total_out_tokens,
            },
            "video_generations_count": video_count,
            "shot_costs": {k: float(v.quantize(FOUR_PLACES)) for k, v in shot_costs.items()},
            "records_count": len(records),
        }

    @classmethod
    async def get_usage_ledger(
        cls,
        session: AsyncSession,
        project_id: uuid.UUID | None = None,
        provider: str | None = None,
        model: str | None = None,
        operation: str | None = None,
        request_status: str | None = None,
        cost_status: str | None = None,
        origin: str | None = UsageOrigin.PRODUCTION.value,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AIUsageRecord], int]:
        """Searchable and paginated usage ledger."""
        query = select(AIUsageRecord)

        if project_id:
            query = query.where(AIUsageRecord.project_id == project_id)
        if provider:
            query = query.where(AIUsageRecord.provider == provider)
        if model:
            query = query.where(AIUsageRecord.model == model)
        if operation:
            query = query.where(AIUsageRecord.operation == operation)
        if request_status:
            query = query.where(AIUsageRecord.request_status == request_status)
        if cost_status:
            query = query.where(AIUsageRecord.cost_status == cost_status)
        if origin and origin.lower() != "all":
            query = query.where(AIUsageRecord.usage_origin == origin.lower())

        query = cls._apply_date_filter(query, AIUsageRecord.created_at, start_date, end_date)

        # Count total
        count_q = select(func.count()).select_from(query.subquery())
        total_count = (await session.execute(count_q)).scalar() or 0

        # Paginated fetch
        query = query.order_by(desc(AIUsageRecord.created_at)).limit(limit).offset(offset)
        records = (await session.execute(query)).scalars().all()
        return list(records), total_count

    @classmethod
    async def export_usage_csv(
        cls,
        session: AsyncSession,
        project_id: uuid.UUID | None = None,
        provider: str | None = None,
        model: str | None = None,
        origin: str | None = UsageOrigin.PRODUCTION.value,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> str:
        """Export filtered usage records to RFC 4180 compliant CSV."""
        records, _ = await cls.get_usage_ledger(
            session=session,
            project_id=project_id,
            provider=provider,
            model=model,
            origin=origin,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
            offset=0,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID",
            "Timestamp",
            "Project ID",
            "Shot ID",
            "Job ID",
            "Usage Origin",
            "Provider",
            "Model",
            "Operation",
            "Request ID",
            "Task ID",
            "Input Tokens",
            "Output Tokens",
            "Cached Tokens",
            "Video Duration (s)",
            "Billing Unit",
            "Unit Price",
            "Estimated Cost (USD)",
            "Actual Cost (USD)",
            "Cost Status",
            "Request Status",
            "Error Code",
        ])

        for r in records:
            writer.writerow([
                str(r.id),
                r.created_at.isoformat() if r.created_at else "",
                str(r.project_id) if r.project_id else "",
                str(r.shot_id) if r.shot_id else "",
                str(r.job_id) if r.job_id else "",
                r.usage_origin,
                r.provider,
                r.model,
                r.operation,
                r.provider_request_id or "",
                r.provider_task_id or "",
                r.input_tokens if r.input_tokens is not None else "",
                r.output_tokens if r.output_tokens is not None else "",
                r.cached_input_tokens if r.cached_input_tokens is not None else "",
                float(r.video_duration_seconds) if r.video_duration_seconds is not None else "",
                r.billing_unit,
                float(r.unit_price),
                float(r.estimated_cost),
                float(r.actual_cost) if r.actual_cost is not None else "",
                r.cost_status,
                r.request_status,
                r.error_code or "",
            ])

        return output.getvalue()
