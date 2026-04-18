from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.interaction import Interaction, LoopMetric, PatternDetection
from app.models.entity import Entity, RiskLevel
from app.models.case import Case, CaseStatus
from app.models.screening import ScreeningResult, MatchStatus
from app.models.transaction import TransactionAlert
from app.schemas.interaction import (
    InteractionResponse, LoopMetricResponse, PatternDetectionResponse, DashboardMetrics,
)
from app.services.loop_service import LoopService
from app.services.pattern_service import PatternDetectionService

router = APIRouter(prefix="/api/loops", tags=["Reinforcing Loops & Analytics"])


@router.get("/metrics")
async def get_loop_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all loop metrics (Learning, Trust, Efficiency, Compliance Strength)."""
    return await LoopService.get_all_loop_metrics(db)


@router.get("/metrics/learning")
async def get_learning_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LoopService.compute_learning_metrics(db)


@router.get("/metrics/trust")
async def get_trust_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LoopService.compute_trust_metrics(db)


@router.get("/metrics/efficiency")
async def get_efficiency_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LoopService.compute_efficiency_metrics(db)


@router.get("/metrics/compliance")
async def get_compliance_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LoopService.compute_compliance_metrics(db)


@router.get("/history", response_model=list[LoopMetricResponse])
async def get_metric_history(
    loop_type: str = Query(None),
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(LoopMetric)
    if loop_type:
        query = query.where(LoopMetric.loop_type == loop_type)
    query = query.order_by(LoopMetric.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [LoopMetricResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/patterns/detect")
async def detect_patterns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run pattern detection engine."""
    patterns = await PatternDetectionService.detect_all_patterns(db)
    return {
        "patterns_detected": len(patterns),
        "patterns": [PatternDetectionResponse.model_validate(p) for p in patterns],
    }


@router.get("/patterns", response_model=list[PatternDetectionResponse])
async def list_patterns(
    pattern_type: str = Query(None),
    severity: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(PatternDetection).where(PatternDetection.is_active == True)
    if pattern_type:
        query = query.where(PatternDetection.pattern_type == pattern_type)
    if severity:
        query = query.where(PatternDetection.severity == severity)
    query = query.order_by(PatternDetection.created_at.desc())
    result = await db.execute(query)
    return [PatternDetectionResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/interactions", response_model=list[InteractionResponse])
async def list_interactions(
    interaction_type: str = Query(None),
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Interaction)
    if interaction_type:
        query = query.where(Interaction.interaction_type == interaction_type)
    query = query.order_by(Interaction.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [InteractionResponse.model_validate(i) for i in result.scalars().all()]


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Main dashboard with all key metrics."""
    # Entity counts
    total_entities = (await db.execute(select(func.count(Entity.id)))).scalar() or 0
    high_risk = (await db.execute(
        select(func.count(Entity.id)).where(Entity.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]))
    )).scalar() or 0

    # Case counts
    total_cases = (await db.execute(select(func.count(Case.id)))).scalar() or 0
    open_cases = (await db.execute(
        select(func.count(Case.id)).where(Case.status.in_([
            CaseStatus.OPEN, CaseStatus.ASSIGNED, CaseStatus.UNDER_INVESTIGATION, CaseStatus.PENDING_DECISION
        ]))
    )).scalar() or 0
    sla_breached = (await db.execute(
        select(func.count(Case.id)).where(Case.sla_breached == True)
    )).scalar() or 0

    # Screening
    pending_screenings = (await db.execute(
        select(func.count(ScreeningResult.id)).where(ScreeningResult.status == MatchStatus.PENDING)
    )).scalar() or 0

    # Metrics
    cases_with_time = await db.execute(
        select(Case.time_to_decision_minutes).where(Case.time_to_decision_minutes.isnot(None))
    )
    times = [r[0] for r in cases_with_time.all()]
    avg_resolution = round(sum(times) / len(times) / 60, 1) if times else 0.0

    # False positive rate
    total_resolved = (await db.execute(
        select(func.count(ScreeningResult.id)).where(ScreeningResult.status != MatchStatus.PENDING)
    )).scalar() or 0
    false_positives = (await db.execute(
        select(func.count(ScreeningResult.id)).where(ScreeningResult.status == MatchStatus.FALSE_POSITIVE)
    )).scalar() or 0
    fp_rate = round(false_positives / total_resolved, 3) if total_resolved > 0 else 0.0

    # AI acceptance rate
    total_ai = (await db.execute(
        select(func.count(Case.id)).where(Case.ai_suggestion_accepted.isnot(None))
    )).scalar() or 0
    accepted_ai = (await db.execute(
        select(func.count(Case.id)).where(Case.ai_suggestion_accepted == True)
    )).scalar() or 0
    ai_rate = round(accepted_ai / total_ai, 3) if total_ai > 0 else 0.0

    # Cases by status
    cases_by_status = {}
    for s in CaseStatus:
        count = (await db.execute(select(func.count(Case.id)).where(Case.status == s))).scalar() or 0
        if count > 0:
            cases_by_status[s.value] = count

    # Cases by priority
    from app.models.case import CasePriority
    cases_by_priority = {}
    for p in CasePriority:
        count = (await db.execute(select(func.count(Case.id)).where(Case.priority == p))).scalar() or 0
        if count > 0:
            cases_by_priority[p.value] = count

    # Risk distribution
    risk_dist = {}
    for rl in RiskLevel:
        count = (await db.execute(select(func.count(Entity.id)).where(Entity.risk_level == rl))).scalar() or 0
        if count > 0:
            risk_dist[rl.value] = count

    # Loop metrics
    loop_metrics = await LoopService.get_all_loop_metrics(db)

    return DashboardMetrics(
        total_entities=total_entities,
        total_cases=total_cases,
        open_cases=open_cases,
        pending_screenings=pending_screenings,
        high_risk_entities=high_risk,
        sla_breached_cases=sla_breached,
        avg_resolution_time_hours=avg_resolution,
        false_positive_rate=fp_rate,
        ai_acceptance_rate=ai_rate,
        cases_by_status=cases_by_status,
        cases_by_priority=cases_by_priority,
        risk_distribution=risk_dist,
        loop_metrics=loop_metrics,
    )
