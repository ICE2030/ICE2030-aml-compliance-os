"""Phase 3: Decision Intelligence API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus
from app.models.intelligence import DecisionCapture, CaseMemoryEntry, CaseCluster
from app.schemas.intelligence import (
    DecisionCaptureCreate,
    DecisionCaptureResponse,
    SimilarCaseResult,
    CaseMemoryResponse,
    CaseClusterResponse,
    OutcomeDashboardResponse,
)
from app.services.intelligence_service import (
    DecisionCaptureService,
    CaseMemoryService,
    IntelligenceLoopService,
    IntelligencePatternService,
    OutcomeDashboardService,
)
from app.services.audit_service import AuditService
from datetime import datetime, timezone

router = APIRouter(prefix="/api/intelligence", tags=["Decision Intelligence"])


# ---------------------------------------------------------------------------
# Decision Capture
# ---------------------------------------------------------------------------

@router.post("/cases/{case_id}/decide", response_model=DecisionCaptureResponse)
async def capture_decision(
    case_id: str,
    data: DecisionCaptureCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Capture a structured case decision with reasoning categories and AI disposition."""
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(status_code=403, detail="Only compliance officers can make decisions")

    # Verify case exists
    case_result = await db.execute(select(Case).where(Case.id == case_id))
    case_obj = case_result.scalar_one_or_none()
    if not case_obj:
        raise HTTPException(status_code=404, detail="Case not found")

    try:
        capture = await DecisionCaptureService.capture_decision(
            db=db,
            case_id=case_id,
            user_id=current_user.id,
            decision=data.decision,
            reasoning_text=data.reasoning_text,
            user_confidence=data.user_confidence,
            reasoning_categories=data.reasoning_categories,
            investigation_time_seconds=data.investigation_time_seconds,
            review_time_seconds=data.review_time_seconds,
            ai_disposition=data.ai_disposition,
        )

        # Also update the case status
        status_map = {
            "no_action": CaseStatus.CLOSED_NO_ACTION,
            "approve": CaseStatus.CLOSED_NO_ACTION,
            "sar_filed": CaseStatus.CLOSED_SAR_FILED,
            "escalate": CaseStatus.ESCALATED,
            "reject": CaseStatus.CLOSED_OTHER,
            "close_other": CaseStatus.CLOSED_OTHER,
        }
        now = datetime.now(timezone.utc)
        case_obj.decision = data.decision
        case_obj.decision_reasoning = data.reasoning_text
        case_obj.decision_confidence = data.user_confidence
        case_obj.decided_by = current_user.id
        case_obj.decided_at = now
        case_obj.status = status_map.get(data.decision, CaseStatus.CLOSED_OTHER)
        case_obj.ai_suggestion_accepted = data.ai_disposition == "accepted" if data.ai_disposition else None

        created = case_obj.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        case_obj.time_to_decision_minutes = int((now - created).total_seconds() / 60) if created else None

        await db.flush()

        await AuditService.log(
            db, "intelligence_decision", "case", case_id, current_user.id,
            {
                "decision": data.decision,
                "confidence": data.user_confidence,
                "ai_disposition": data.ai_disposition,
                "reasoning_categories": data.reasoning_categories,
            }
        )

        return DecisionCaptureResponse.model_validate(capture)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/decisions", response_model=list[DecisionCaptureResponse])
async def get_case_decisions(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all decision captures for a case."""
    decisions = await DecisionCaptureService.get_case_decisions(db, case_id)
    return [DecisionCaptureResponse.model_validate(d) for d in decisions]


@router.get("/decisions/recent", response_model=list[DecisionCaptureResponse])
async def list_recent_decisions(
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent decision captures across all cases."""
    decisions = await DecisionCaptureService.list_recent_decisions(db, limit)
    return [DecisionCaptureResponse.model_validate(d) for d in decisions]


# ---------------------------------------------------------------------------
# Case Memory / Similarity Search
# ---------------------------------------------------------------------------

@router.get("/cases/{case_id}/similar", response_model=list[SimilarCaseResult])
async def find_similar_cases(
    case_id: str,
    limit: int = Query(default=5, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find similar past cases using semantic + structured similarity."""
    results = await CaseMemoryService.find_similar_cases(db, case_id, limit)

    await AuditService.log(
        db, "similar_case_search", "case", case_id, current_user.id,
        {"results_count": len(results)}
    )

    return [SimilarCaseResult(**r) for r in results]


@router.get("/memory", response_model=list[CaseMemoryResponse])
async def list_case_memories(
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all case memory entries."""
    result = await db.execute(
        select(CaseMemoryEntry).order_by(CaseMemoryEntry.created_at.desc()).limit(limit)
    )
    return [CaseMemoryResponse.model_validate(m) for m in result.scalars().all()]


# ---------------------------------------------------------------------------
# Loop Instrumentation
# ---------------------------------------------------------------------------

@router.get("/loops")
async def get_loop_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all four instrumented loop metrics."""
    return await IntelligenceLoopService.compute_all_loops(db)


@router.get("/loops/decision")
async def get_decision_loop(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await IntelligenceLoopService.compute_decision_loop(db)


@router.get("/loops/false-positive")
async def get_false_positive_loop(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await IntelligenceLoopService.compute_false_positive_loop(db)


@router.get("/loops/efficiency")
async def get_efficiency_loop(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await IntelligenceLoopService.compute_efficiency_loop(db)


@router.get("/loops/trust")
async def get_trust_loop(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await IntelligenceLoopService.compute_trust_loop(db)


# ---------------------------------------------------------------------------
# Pattern Detection
# ---------------------------------------------------------------------------

@router.post("/patterns/detect", response_model=list[CaseClusterResponse])
async def detect_patterns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the pattern detection engine to identify case clusters."""
    clusters = await IntelligencePatternService.detect_case_clusters(db)

    await AuditService.log(
        db, "pattern_detection", "intelligence", "system", current_user.id,
        {"clusters_detected": len(clusters)}
    )

    return [CaseClusterResponse.model_validate(c) for c in clusters]


@router.get("/patterns", response_model=list[CaseClusterResponse])
async def list_patterns(
    cluster_type: str = Query(None),
    severity: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active case clusters / patterns."""
    query = select(CaseCluster).where(CaseCluster.is_active == True)
    if cluster_type:
        query = query.where(CaseCluster.cluster_type == cluster_type)
    if severity:
        query = query.where(CaseCluster.severity == severity)
    query = query.order_by(CaseCluster.created_at.desc())
    result = await db.execute(query)
    return [CaseClusterResponse.model_validate(c) for c in result.scalars().all()]


# ---------------------------------------------------------------------------
# Outcome Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def get_intelligence_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive intelligence dashboard data."""
    return await OutcomeDashboardService.get_dashboard_data(db)
