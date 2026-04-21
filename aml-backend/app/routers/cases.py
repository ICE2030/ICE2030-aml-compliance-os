import random
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.case import Case, CaseNote, CaseStatus, CaseType, CasePriority
from app.schemas.case import (
    CaseCreate, CaseUpdate, CaseResponse, CaseDecision,
    CaseNoteCreate, CaseNoteResponse,
)
from app.services.audit_service import AuditService
from app.services.ai_service import AIAssistantService
from app.services.intelligence_service import DecisionCaptureService
from app.models.base import generate_uuid
from app.models.interaction import Interaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["Case Management"])


def generate_case_number():
    return f"CASE-{random.randint(100000, 999999)}"


@router.post("/", response_model=CaseResponse)
@router.post("", response_model=CaseResponse, include_in_schema=False)
async def create_case(
    data: CaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sla_deadline = None
    if data.sla_hours:
        sla_deadline = datetime.now(timezone.utc) + timedelta(hours=data.sla_hours)

    case = Case(
        id=generate_uuid(),
        case_number=generate_case_number(),
        entity_id=data.entity_id,
        case_type=CaseType(data.case_type),
        priority=CasePriority(data.priority),
        title=data.title,
        description=data.description,
        assigned_to=data.assigned_to,
        sla_deadline=sla_deadline,
    )
    db.add(case)
    await db.flush()

    # Generate AI summary
    try:
        summary_data = await AIAssistantService.summarize_case(db, case.id)
        case.ai_summary = summary_data["summary"]
        suggestion_data = await AIAssistantService.suggest_decision(db, case.id)
        case.ai_suggestion = f"{suggestion_data['suggestion']}: {suggestion_data['reasoning']}"
        await db.flush()
    except Exception:
        pass

    await AuditService.log(
        db, "create_case", "case", case.id, current_user.id,
        {"case_number": case.case_number, "type": data.case_type, "priority": data.priority}
    )
    return CaseResponse.model_validate(case)


@router.get("/", response_model=list[CaseResponse])
@router.get("", response_model=list[CaseResponse], include_in_schema=False)
async def list_cases(
    status: str = Query(None),
    priority: str = Query(None),
    case_type: str = Query(None),
    assigned_to: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Case)
    if status:
        query = query.where(Case.status == CaseStatus(status))
    if priority:
        query = query.where(Case.priority == CasePriority(priority))
    if case_type:
        query = query.where(Case.case_type == CaseType(case_type))
    if assigned_to:
        query = query.where(Case.assigned_to == assigned_to)
    query = query.offset(skip).limit(limit).order_by(Case.created_at.desc())
    result = await db.execute(query)
    return [CaseResponse.model_validate(c) for c in result.scalars().all()]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Check SLA (handle naive datetimes from SQLite)
    sla = case.sla_deadline
    if sla and sla.tzinfo is None:
        sla = sla.replace(tzinfo=timezone.utc)
    if sla and datetime.now(timezone.utc) > sla and not case.sla_breached:
        case.sla_breached = True
        await db.flush()

    await AuditService.log(db, "view_case", "case", case_id, current_user.id)
    return CaseResponse.model_validate(case)


@router.put("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: str,
    data: CaseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data:
        update_data["status"] = CaseStatus(update_data["status"])
    if "priority" in update_data:
        update_data["priority"] = CasePriority(update_data["priority"])
    for field, value in update_data.items():
        setattr(case, field, value)

    await db.flush()
    await AuditService.log(db, "update_case", "case", case_id, current_user.id, update_data)
    return CaseResponse.model_validate(case)


@router.post("/{case_id}/decide", response_model=CaseResponse)
async def decide_case(
    case_id: str,
    decision: CaseDecision,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Make a case decision with structured interaction capture."""
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(status_code=403, detail="Only compliance officers can make decisions")

    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.now(timezone.utc)
    created = case.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    time_to_decision = int((now - created).total_seconds() / 60) if created else None

    status_map = {
        "no_action": CaseStatus.CLOSED_NO_ACTION,
        "sar_filed": CaseStatus.CLOSED_SAR_FILED,
        "escalate": CaseStatus.ESCALATED,
        "close_other": CaseStatus.CLOSED_OTHER,
    }

    # Bridge to Phase 3 intelligence layer BEFORE updating case fields,
    # so capture_decision reads the original ai_suggestion_confidence (not user's).
    ai_disposition = None
    if decision.ai_suggestion_accepted is True:
        ai_disposition = "accepted"
    elif decision.ai_suggestion_accepted is False:
        ai_disposition = "rejected"

    try:
        await DecisionCaptureService.capture_decision(
            db=db,
            case_id=case_id,
            user_id=current_user.id,
            decision=decision.decision,
            reasoning_text=decision.reasoning,
            user_confidence=decision.confidence_level,
            reasoning_categories=None,
            investigation_time_seconds=None,
            review_time_seconds=None,
            ai_disposition=ai_disposition,
        )
    except Exception as e:
        logger.warning(f"Failed to create DecisionCapture for case {case_id}: {e}")

    # Now update case fields (after capture_decision read the original values)
    case.decision = decision.decision
    case.decision_reasoning = decision.reasoning
    case.decision_confidence = decision.confidence_level
    case.decided_by = current_user.id
    case.decided_at = now
    case.status = status_map.get(decision.decision, CaseStatus.CLOSED_OTHER)
    case.time_to_decision_minutes = time_to_decision
    case.ai_suggestion_accepted = decision.ai_suggestion_accepted

    await db.flush()
    await AuditService.log(
        db, "case_decision", "case", case_id, current_user.id,
        {
            "decision": decision.decision,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence_level,
            "time_to_decision_minutes": time_to_decision,
        }
    )
    return CaseResponse.model_validate(case)


@router.post("/{case_id}/notes", response_model=CaseNoteResponse)
async def add_case_note(
    case_id: str,
    data: CaseNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = CaseNote(
        id=generate_uuid(),
        case_id=case_id,
        user_id=current_user.id,
        content=data.content,
        note_type=data.note_type,
    )
    db.add(note)
    await db.flush()
    await AuditService.log(db, "add_case_note", "case_note", note.id, current_user.id)
    return CaseNoteResponse.model_validate(note)


@router.get("/{case_id}/notes", response_model=list[CaseNoteResponse])
async def list_case_notes(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CaseNote).where(CaseNote.case_id == case_id).order_by(CaseNote.created_at.desc())
    )
    return [CaseNoteResponse.model_validate(n) for n in result.scalars().all()]


@router.get("/{case_id}/ai/summary")
async def get_ai_summary(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await AIAssistantService.summarize_case(db, case_id)
    await AuditService.log(db, "ai_summary_requested", "case", case_id, current_user.id)
    return summary


@router.get("/{case_id}/ai/suggestion")
async def get_ai_suggestion(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await AIAssistantService.suggest_decision(db, case_id)
    await AuditService.log(db, "ai_suggestion_requested", "case", case_id, current_user.id)
    return suggestion


@router.get("/{case_id}/ai/similar")
async def get_similar_cases(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    similar = await AIAssistantService.find_similar_cases(db, case_id)
    return {"case_id": case_id, "similar_cases": similar}
