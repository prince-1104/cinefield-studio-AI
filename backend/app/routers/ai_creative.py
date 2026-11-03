"""AI Creative Director and Website Analysis endpoints."""

import logging
from fastapi import APIRouter, HTTPException, status

from app.schemas.creative_ai import (
    CreativeBriefRequest,
    GeneratedBriefResponse,
    ImportAssetRequest,
    ImportAssetResponse,
    WebsiteAnalysisRequest,
    WebsiteAnalysisResult,
)
from app.services.creative_director import creative_director
from app.services.website_analyzer import analyze_website, import_website_asset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Creative Director"])


@router.post(
    "/analyze-website",
    response_model=WebsiteAnalysisResult,
    summary="Analyze website for brand identity, messaging, and visual assets",
)
async def analyze_website_endpoint(payload: WebsiteAnalysisRequest) -> WebsiteAnalysisResult:
    """Analyze a public website to extract page metadata, messaging highlights, logos, and product imagery."""
    try:
        return await analyze_website(payload.url)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Website analysis error for '{payload.url}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not analyze website: {exc}",
        )


@router.post(
    "/generate-brief",
    response_model=GeneratedBriefResponse,
    summary="Generate full cinematic production brief with Claude AI Creative Director",
)
async def generate_brief_endpoint(payload: CreativeBriefRequest) -> GeneratedBriefResponse:
    """Transform user prompt, category preferences, and optional website data into a production brief."""
    try:
        return await creative_director.generate_brief(payload)
    except Exception as exc:
        logger.error(f"Claude creative brief generation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Creative brief generation failed: {exc}",
        )


@router.post(
    "/import-asset",
    response_model=ImportAssetResponse,
    summary="Download discovered website asset to local artifact storage",
)
async def import_asset_endpoint(payload: ImportAssetRequest) -> ImportAssetResponse:
    """Safely stream and persist a selected image from website analysis into Pexyl artifact storage."""
    try:
        file_path, file_name, file_size, content_type = await import_website_asset(
            asset_url=payload.url,
            project_id=payload.project_id,
            asset_type=payload.asset_type,
        )
        return ImportAssetResponse(
            asset_path=file_path,
            url=payload.url,
            file_name=file_name,
            size=file_size,
            content_type=content_type,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Asset import failed for '{payload.url}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to import asset: {exc}",
        )

