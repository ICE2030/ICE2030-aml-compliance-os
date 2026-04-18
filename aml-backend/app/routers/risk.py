from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.risk import RiskRule, RiskAssessment
from app.models.entity import Entity, RiskLevel
from app.schemas.risk import RiskRuleCreate, RiskRuleResponse, RiskAssessmentResponse, RiskOverride
from app.services.risk_service import RiskScoringService
from app.services.audit_service import AuditService
from app.models.base import generate_uuid
from app.models.interaction import Interaction

router = APIRouter(prefix="/api/risk", tags=["Risk Scoring Engine"])


@router.post("/assess/{entity_id}", response_model=RiskAssessmentResponse)
async def assess_entity_risk(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assessment = await RiskScoringService.assess_entity(db, entity_id, current_user.id)
    await AuditService.log(
        db, "risk_assessment", "risk_assessment", assessment.id, current_user.id,
        {"entity_id": entity_id, "score": assessment.total_score, "level": assessment.risk_level}
    )
    return RiskAssessmentResponse.model_validate(assessment)


@router.post("/assess/{entity_id}/override", response_model=RiskAssessmentResponse)
async def override_risk(
    entity_id: str,
    override: RiskOverride,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(status_code=403, detail="Only compliance officers can override risk")

    result = await db.execute(
        select(RiskAssessment).where(RiskAssessment.entity_id == entity_id)
        .order_by(RiskAssessment.created_at.desc()).limit(1)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found")

    assessment.is_overridden = True
    assessment.override_level = override.override_level
    assessment.override_reasoning = override.reasoning

    # Update entity
    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    if entity:
        entity.risk_level = RiskLevel(override.override_level)

    # Capture interaction
    interaction = Interaction(
        id=generate_uuid(),
        user_id=current_user.id,
        interaction_type="risk_override",
        action="override_risk_level",
        resource_type="risk_assessment",
        resource_id=assessment.id,
        decision=override.override_level,
        reasoning=override.reasoning,
        confidence_level=override.confidence_level,
    )
    db.add(interaction)

    await db.flush()
    await AuditService.log(
        db, "risk_override", "risk_assessment", assessment.id, current_user.id,
        {"from_level": assessment.risk_level, "to_level": override.override_level, "reasoning": override.reasoning}
    )
    return RiskAssessmentResponse.model_validate(assessment)


@router.get("/assessments", response_model=list[RiskAssessmentResponse])
async def list_assessments(
    entity_id: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(RiskAssessment)
    if entity_id:
        query = query.where(RiskAssessment.entity_id == entity_id)
    query = query.offset(skip).limit(limit).order_by(RiskAssessment.created_at.desc())
    result = await db.execute(query)
    return [RiskAssessmentResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/rules", response_model=RiskRuleResponse)
async def create_risk_rule(
    data: RiskRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(status_code=403, detail="Not authorized")
    rule = RiskRule(
        id=generate_uuid(),
        organization_id=current_user.organization_id or "",
        name=data.name,
        description=data.description,
        category=data.category,
        field=data.field,
        operator=data.operator,
        value=data.value,
        score_impact=data.score_impact,
        weight=data.weight,
        is_active=data.is_active,
    )
    db.add(rule)
    await db.flush()
    await AuditService.log(db, "create_risk_rule", "risk_rule", rule.id, current_user.id)
    return RiskRuleResponse.model_validate(rule)


@router.get("/rules", response_model=list[RiskRuleResponse])
async def list_risk_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(RiskRule)
    if current_user.organization_id:
        query = query.where(RiskRule.organization_id == current_user.organization_id)
    result = await db.execute(query)
    return [RiskRuleResponse.model_validate(r) for r in result.scalars().all()]
