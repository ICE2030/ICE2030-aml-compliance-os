from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.entity import Entity, OwnershipLink, OnboardingStatus, EntityType, Document
from app.schemas.entity import (
    EntityCreate, EntityUpdate, EntityResponse,
    OwnershipLinkCreate, OwnershipLinkResponse, OnboardingAction,
)
from app.services.audit_service import AuditService
from app.services.screening_service import ScreeningService
from app.services.risk_service import RiskScoringService
from app.models.base import generate_uuid
from app.models.interaction import Interaction

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding & KYB/KYC"])


@router.post("/entities", response_model=EntityResponse)
async def create_entity(
    data: EntityCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = Entity(
        id=generate_uuid(),
        organization_id=current_user.organization_id or "",
        entity_type=EntityType(data.entity_type),
        name=data.name,
        name_ar=data.name_ar,
        national_id=data.national_id,
        date_of_birth=data.date_of_birth,
        nationality=data.nationality,
        registration_number=data.registration_number,
        license_number=data.license_number,
        incorporation_date=data.incorporation_date,
        industry=data.industry,
        country=data.country,
        address=data.address,
        phone=data.phone,
        email=data.email,
        onboarding_status=OnboardingStatus.PENDING_REVIEW,
        additional_data=data.additional_data,
    )
    db.add(entity)
    await db.flush()
    await AuditService.log(db, "create_entity", "entity", entity.id, current_user.id, {"name": data.name, "type": data.entity_type})

    # Auto-screen
    try:
        await ScreeningService.screen_entity(db, entity.id, ["sanctions", "pep"])
    except Exception:
        pass

    # Auto-risk assess
    try:
        await RiskScoringService.assess_entity(db, entity.id, current_user.id)
    except Exception:
        pass

    await db.refresh(entity)
    return EntityResponse.model_validate(entity)


@router.get("/entities", response_model=list[EntityResponse])
async def list_entities(
    status: str = Query(None),
    entity_type: str = Query(None),
    search: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Entity)
    if current_user.organization_id:
        query = query.where(Entity.organization_id == current_user.organization_id)
    if status:
        query = query.where(Entity.onboarding_status == OnboardingStatus(status))
    if entity_type:
        query = query.where(Entity.entity_type == EntityType(entity_type))
    if search:
        query = query.where(Entity.name.ilike(f"%{search}%"))
    query = query.offset(skip).limit(limit).order_by(Entity.created_at.desc())
    result = await db.execute(query)
    return [EntityResponse.model_validate(e) for e in result.scalars().all()]


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    await AuditService.log(db, "view_entity", "entity", entity_id, current_user.id)
    return EntityResponse.model_validate(entity)


@router.put("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    data: EntityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    update_data = data.model_dump(exclude_unset=True)
    if "onboarding_status" in update_data:
        update_data["onboarding_status"] = OnboardingStatus(update_data["onboarding_status"])
    for field, value in update_data.items():
        setattr(entity, field, value)

    await db.flush()
    await AuditService.log(db, "update_entity", "entity", entity_id, current_user.id, update_data)
    return EntityResponse.model_validate(entity)


@router.post("/entities/{entity_id}/review", response_model=EntityResponse)
async def review_entity(
    entity_id: str,
    action: OnboardingAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Onboarding review with structured interaction capture."""
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    status_map = {
        "approve": OnboardingStatus.APPROVED,
        "reject": OnboardingStatus.REJECTED,
        "request_info": OnboardingStatus.REQUIRES_INFO,
    }
    new_status = status_map.get(action.action)
    if not new_status:
        raise HTTPException(status_code=400, detail="Invalid action")

    entity.onboarding_status = new_status
    await db.flush()

    # Capture structured interaction
    interaction = Interaction(
        id=generate_uuid(),
        user_id=current_user.id,
        interaction_type="onboarding_review",
        action=action.action,
        resource_type="entity",
        resource_id=entity_id,
        decision=action.action,
        reasoning=action.reasoning,
        confidence_level=action.confidence_level,
    )
    db.add(interaction)

    await AuditService.log(
        db, f"onboarding_{action.action}", "entity", entity_id, current_user.id,
        {"reasoning": action.reasoning, "confidence": action.confidence_level}
    )

    return EntityResponse.model_validate(entity)


@router.post("/entities/{entity_id}/ownership", response_model=OwnershipLinkResponse)
async def add_ownership_link(
    entity_id: str,
    data: OwnershipLinkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = OwnershipLink(
        id=generate_uuid(),
        parent_entity_id=data.parent_entity_id,
        child_entity_id=data.child_entity_id,
        ownership_percentage=data.ownership_percentage,
        relationship_type=data.relationship_type,
        is_ubo=data.is_ubo,
        is_direct=data.is_direct,
    )
    db.add(link)
    await db.flush()
    await AuditService.log(db, "add_ownership", "ownership_link", link.id, current_user.id)
    return OwnershipLinkResponse.model_validate(link)


@router.get("/entities/{entity_id}/ownership", response_model=list[OwnershipLinkResponse])
async def get_ownership_structure(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OwnershipLink).where(
            (OwnershipLink.parent_entity_id == entity_id) |
            (OwnershipLink.child_entity_id == entity_id)
        )
    )
    links = result.scalars().all()
    return [OwnershipLinkResponse.model_validate(l) for l in links]


@router.get("/entities/{entity_id}/ubo")
async def determine_ubo(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """UBO determination - find ultimate beneficial owners."""
    result = await db.execute(
        select(OwnershipLink).where(OwnershipLink.child_entity_id == entity_id)
    )
    links = result.scalars().all()

    ubos = []
    for link in links:
        if link.ownership_percentage >= 25 or link.is_ubo:
            parent_result = await db.execute(select(Entity).where(Entity.id == link.parent_entity_id))
            parent = parent_result.scalar_one_or_none()
            if parent:
                ubos.append({
                    "entity_id": parent.id,
                    "name": parent.name,
                    "ownership_percentage": link.ownership_percentage,
                    "relationship_type": link.relationship_type,
                    "is_direct": link.is_direct,
                    "entity_type": parent.entity_type.value,
                })

    await AuditService.log(db, "determine_ubo", "entity", entity_id, current_user.id)
    return {"entity_id": entity_id, "ubos": ubos, "total_ubos": len(ubos)}
