from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.screening import ScreeningResult, MatchStatus
from app.schemas.screening import ScreeningRequest, ScreeningResultResponse, MatchResolution
from app.services.screening_service import ScreeningService
from app.services.audit_service import AuditService
from app.models.base import generate_uuid
from app.models.interaction import Interaction

router = APIRouter(prefix="/api/screening", tags=["Screening Engine"])


@router.get("/data-sources")
async def get_data_sources(
    current_user: User = Depends(get_current_user),
):
    """Get information about screening data sources (UN Sanctions, PEP, etc.)."""
    return await ScreeningService.get_data_source_info()


@router.post("/screen", response_model=list[ScreeningResultResponse])
async def screen_entity(
    data: ScreeningRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await ScreeningService.screen_entity(db, data.entity_id, data.screening_types)
    await AuditService.log(
        db, "screen_entity", "screening", data.entity_id, current_user.id,
        {"types": data.screening_types, "results_count": len(results)}
    )
    return [ScreeningResultResponse.model_validate(r) for r in results]


@router.get("/results", response_model=list[ScreeningResultResponse])
async def list_screening_results(
    entity_id: str = Query(None),
    status: str = Query(None),
    screening_type: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ScreeningResult)
    if entity_id:
        query = query.where(ScreeningResult.entity_id == entity_id)
    if status:
        query = query.where(ScreeningResult.status == MatchStatus(status))
    if screening_type:
        query = query.where(ScreeningResult.screening_type == screening_type)
    query = query.offset(skip).limit(limit).order_by(ScreeningResult.created_at.desc())
    result = await db.execute(query)
    return [ScreeningResultResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/results/{result_id}", response_model=ScreeningResultResponse)
async def get_screening_result(
    result_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ScreeningResult).where(ScreeningResult.id == result_id))
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=404, detail="Screening result not found")
    return ScreeningResultResponse.model_validate(sr)


@router.post("/results/{result_id}/resolve", response_model=ScreeningResultResponse)
async def resolve_screening(
    result_id: str,
    resolution: MatchResolution,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a screening match with structured interaction capture."""
    result = await db.execute(select(ScreeningResult).where(ScreeningResult.id == result_id))
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=404, detail="Screening result not found")

    sr.status = MatchStatus(resolution.status)
    sr.resolved_by = current_user.id
    sr.resolution_reasoning = resolution.reasoning
    sr.resolution_confidence = resolution.confidence_level

    # Capture structured interaction
    interaction = Interaction(
        id=generate_uuid(),
        user_id=current_user.id,
        interaction_type="screening_resolution",
        action=f"resolve_{resolution.status}",
        resource_type="screening_result",
        resource_id=result_id,
        decision=resolution.status,
        reasoning=resolution.reasoning,
        confidence_level=resolution.confidence_level,
        ai_suggestion_given=sr.ai_suggestion,
        ai_suggestion_accepted=resolution.ai_suggestion_accepted,
    )
    db.add(interaction)

    await db.flush()
    await AuditService.log(
        db, "resolve_screening", "screening_result", result_id, current_user.id,
        {"status": resolution.status, "reasoning": resolution.reasoning, "confidence": resolution.confidence_level}
    )
    return ScreeningResultResponse.model_validate(sr)
