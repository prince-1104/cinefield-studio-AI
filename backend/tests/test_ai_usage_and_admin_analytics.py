"""Comprehensive backend tests for AI usage ledger, model pricing, cost analytics, and admin APIs."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.main import create_app
from app.models.ai_usage import AIModelPricing, AIUsageRecord, BillingUnit, CostStatus, RequestStatus
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.services.ai_usage_service import (
    AIUsageService,
    calculate_token_cost,
    calculate_video_cost,
    get_effective_pricing,
    seed_default_pricing,
)


@pytest.mark.asyncio
async def test_seed_and_effective_pricing_lookup():
    """Verify default pricing models are seeded and version lookup works."""
    async with async_session_factory() as db_session:
        await seed_default_pricing(db_session)

        pricing_claude = await get_effective_pricing(db_session, "claude", "claude-3-7-sonnet-20250219")
        assert pricing_claude is not None
        assert pricing_claude.billing_unit == "tokens"
        assert pricing_claude.input_price_per_million == Decimal("3.000000")
        assert pricing_claude.output_price_per_million == Decimal("15.000000")

        pricing_seedance = await get_effective_pricing(db_session, "seedance", "dreamina-seedance-2-5-260628")
        assert pricing_seedance is not None
        assert pricing_seedance.billing_unit == "video_seconds"
        assert pricing_seedance.video_price_per_second == Decimal("0.050000")


@pytest.mark.asyncio
async def test_decimal_cost_calculations():
    """Verify financial precision using Decimal arithmetic for token and video models."""
    async with async_session_factory() as db_session:
        await seed_default_pricing(db_session)
        pricing = await get_effective_pricing(db_session, "claude", "claude-3-7-sonnet-20250219")

        # 10,000 input tokens ($0.030) + 1,000 output tokens ($0.015) = $0.045
        total, in_cost, out_cost = calculate_token_cost(
            input_tokens=10000,
            output_tokens=1000,
            cached_tokens=None,
            pricing=pricing,
        )
        assert total == Decimal("0.045000")
        assert in_cost == Decimal("0.030000")
        assert out_cost == Decimal("0.015000")

        # Seedance: 6.0 seconds @ $0.05/sec = $0.300000
        seedance_pricing = await get_effective_pricing(db_session, "seedance", "dreamina-seedance-2-5-260628")
        video_cost = calculate_video_cost(6.0, seedance_pricing)
        assert video_cost == Decimal("0.300000")


@pytest.mark.asyncio
async def test_record_claude_usage_and_ledger():
    """Verify recording of Claude API calls with token tracking into the ledger."""
    async with async_session_factory() as db_session:
        await seed_default_pricing(db_session)

        record = await AIUsageService.record_claude_usage(
            session=db_session,
            model="claude-3-7-sonnet-20250219",
            operation="creative_brief",
            input_tokens=2500,
            output_tokens=600,
            provider_request_id="msg_test_12345",
        )
        await db_session.commit()

        assert record.id is not None
        assert record.provider == "claude"
        assert record.model == "claude-3-7-sonnet-20250219"
        assert record.input_tokens == 2500
        assert record.output_tokens == 600
        assert record.provider_request_id == "msg_test_12345"
        assert record.estimated_cost > Decimal("0")
        assert record.cost_status == CostStatus.ACTUAL.value


@pytest.mark.asyncio
async def test_record_seedance_usage_and_retry_accounting():
    """Verify Seedance video generation and retry tracking create distinct records."""
    async with async_session_factory() as db_session:
        await seed_default_pricing(db_session)

        # Create real project to satisfy foreign key constraint
        project = Project(
            product_name="Test Product",
            brief="Test brief",
            audience="Testers",
            tone="cinematic",
            cta="Buy now",
        )
        db_session.add(project)
        await db_session.flush()

        # Initial video generation attempt
        rec1 = await AIUsageService.record_seedance_usage(
            session=db_session,
            model="dreamina-seedance-2-5-260628",
            operation="video_generation",
            duration_seconds=5.0,
            provider_task_id="task_seedance_001",
            project_id=project.id,
            request_status="SUCCESS",
        )

        # Retry generation attempt
        rec2 = await AIUsageService.record_seedance_usage(
            session=db_session,
            model="dreamina-seedance-2-5-260628",
            operation="video_retry",
            duration_seconds=5.0,
            provider_task_id="task_seedance_002",
            project_id=project.id,
            request_status="SUCCESS",
        )
        await db_session.commit()

        assert rec1.id != rec2.id
        assert rec1.operation == "video_generation"
        assert rec2.operation == "video_retry"
        assert rec1.estimated_cost == Decimal("0.250000")
        assert rec2.estimated_cost == Decimal("0.250000")


@pytest.mark.asyncio
async def test_reconciliation_actual_billing():
    """Verify reconciling estimated application costs with actual provider charges."""
    async with async_session_factory() as db_session:
        await seed_default_pricing(db_session)
        unique_task_id = f"task_reconcile_{uuid.uuid4()}"

        rec = await AIUsageService.record_seedance_usage(
            session=db_session,
            model="dreamina-seedance-2-5-260628",
            operation="video_generation",
            duration_seconds=5.0,
            provider_task_id=unique_task_id,
            request_status="SUCCESS",
        )
        await db_session.commit()
        assert rec.actual_cost is None
        assert rec.cost_status == CostStatus.ESTIMATED.value

        # Reconcile with actual provider billing
        success = await AIUsageService.reconcile_task_billing(
            session=db_session,
            provider_task_id=unique_task_id,
            actual_cost=Decimal("0.220000"),
        )
        await db_session.commit()
        assert success is True

        await db_session.refresh(rec)
        assert rec.actual_cost == Decimal("0.220000")
        assert rec.cost_status == CostStatus.RECONCILED.value


@pytest.mark.asyncio
async def test_admin_api_auth_protection():
    """Verify /api/admin endpoints strictly reject unauthorized requests."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. No key -> 401
        res = await client.get("/api/admin/metrics/overview")
        assert res.status_code == 401

        # 2. Wrong key -> 401
        res = await client.get("/api/admin/metrics/overview", headers={"X-Admin-Key": "wrong-key"})
        assert res.status_code == 401

        # 3. Valid key -> 200
        res = await client.get(
            "/api/admin/metrics/overview",
            headers={"X-Admin-Key": settings.ADMIN_API_KEY},
        )
        assert res.status_code == 200
        data = res.json()
        assert "total_spend" in data
        assert "total_requests" in data


@pytest.mark.asyncio
async def test_admin_csv_export():
    """Verify CSV export of filtered AI usage ledger."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/admin/usage/export-csv",
            headers={"X-Admin-Key": settings.ADMIN_API_KEY},
        )
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert "attachment; filename=" in res.headers["content-disposition"]
        lines = res.text.strip().split("\n")
        assert len(lines) >= 1
        assert "Timestamp,Project ID,Shot ID" in lines[0] or "Timestamp" in lines[0]
