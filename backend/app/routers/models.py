"""Dynamic AI Model Discovery and Capabilities API Router."""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status

from app.services.model_registry import model_registry
from app.services.providers.base import ModelSpec

router = APIRouter(prefix="/api/models", tags=["Model Registry"])


@router.get("", response_model=list[ModelSpec])
async def list_models(
    capability: str | None = Query(default=None, description="Filter by capability (e.g. video_generation, text_generation, speech_generation)"),
    include_unavailable: bool = Query(default=True, description="Whether to include models with missing credentials/unconfigured keys"),
) -> list[ModelSpec]:
    """Discover all registered AI models across capabilities with dynamic availability."""
    return model_registry.list_models(capability=capability, include_unavailable=include_unavailable)


@router.get("/by-capability/{capability}", response_model=list[ModelSpec])
async def list_models_by_capability(
    capability: str,
    include_unavailable: bool = Query(default=True),
) -> list[ModelSpec]:
    """Discover models matching a specific capability (e.g. video_generation, text_generation, speech_generation)."""
    return model_registry.list_models(capability=capability, include_unavailable=include_unavailable)


@router.get("/detail/{model_id}", response_model=ModelSpec)
async def get_model_detail(model_id: str) -> ModelSpec:
    """Retrieve detailed specification, supported parameters, and credentials readiness for a model."""
    spec = model_registry.get_model(model_id)
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' is not registered in the dynamic model registry.",
        )
    return spec
