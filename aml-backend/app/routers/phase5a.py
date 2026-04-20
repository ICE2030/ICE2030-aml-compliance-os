"""Phase 5A API Router: Improved Extraction, Control Suggestions, Evidence Expiry Alerts."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.regulatory.phase5a_service import (
    ImprovedExtractionService,
    ControlSuggestionService,
    EvidenceExpiryAlertService,
)

router = APIRouter(prefix="/api/phase5a", tags=["Phase 5A - Extraction, Suggestions, Alerts"])


# ═══════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════

class AcceptSuggestionRequest(BaseModel):
    control_name: Optional[str] = None
    control_name_ar: Optional[str] = None
    control_type: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    owner: Optional[str] = None
    frequency: Optional[str] = None


class UpdateExpiryRequest(BaseModel):
    expires_at: str  # ISO datetime string


# ═══════════════════════════════════════════════════════════════════════
# 1. Improved Obligation Extraction (v2)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/extract/{provision_id}")
async def extract_obligations_v2(provision_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Extract obligations from a provision using improved v2 extractor.

    Improvements: better classification (guidance, definition), reduced duplicates,
    improved applicability detection, Arabic/English consistency.
    """
    obligations = await ImprovedExtractionService.extract_from_provision_v2(db, provision_id)
    await db.commit()
    return {
        "provision_id": provision_id,
        "extracted": len(obligations),
        "extractor_version": "v2_improved",
        "obligations": [
            {
                "id": ob.id,
                "text": ob.text[:300],
                "obligation_type": ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type),
                "confidence": ob.confidence,
                "criticality": ob.criticality,
                "applies_to_entity_types": ob.applies_to_entity_types,
                "applies_to_product_types": ob.applies_to_product_types,
                "condition": ob.condition,
                "deadline": ob.deadline,
            }
            for ob in obligations
        ],
    }


@router.post("/extract-all")
async def extract_all_v2(
    force: bool = Query(False, description="Delete existing obligations and re-extract"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract obligations from ALL provisions using improved v2 logic.

    Use force=true to delete existing and re-extract with v2.
    """
    result = await ImprovedExtractionService.extract_all_v2(db, force=force)
    await db.commit()
    return result


@router.get("/compare/{provision_id}")
async def compare_extraction(provision_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Compare v1 vs v2 extraction on a single provision.

    Returns side-by-side before/after for evaluation.
    """
    return await ImprovedExtractionService.get_extraction_comparison(db, provision_id)


# ═══════════════════════════════════════════════════════════════════════
# 2. Automated Control Suggestions
# ═══════════════════════════════════════════════════════════════════════

@router.get("/suggestions/{obligation_id}")
async def get_control_suggestion(obligation_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Generate a control suggestion for a single obligation.

    Returns suggested control with name, objective, type, owner, frequency,
    rationale, confidence. Clearly marked as suggestion requiring human review.
    """
    suggestion = await ControlSuggestionService.suggest_controls_for_obligation(db, obligation_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return suggestion


@router.get("/suggestions")
async def get_all_control_suggestions(
    only_unmapped: bool = Query(True, description="Only suggest for obligations without controls"),
    min_confidence: float = Query(0.0, description="Minimum suggestion confidence"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate control suggestions for all (or unmapped) obligations.

    Each suggestion is clearly marked as pending human review.
    """
    suggestions = await ControlSuggestionService.suggest_controls_for_all(
        db, only_unmapped=only_unmapped, min_confidence=min_confidence,
    )
    return {
        "total_suggestions": len(suggestions),
        "only_unmapped": only_unmapped,
        "min_confidence": min_confidence,
        "suggestions": suggestions,
    }


@router.post("/suggestions/{obligation_id}/accept")
async def accept_control_suggestion(
    obligation_id: str,
    data: AcceptSuggestionRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a control suggestion — creates a real control and maps it to the obligation.

    Optionally override suggested fields before accepting.
    """
    if data is None:
        data = AcceptSuggestionRequest()

    result = await ControlSuggestionService.accept_suggestion(
        db,
        obligation_id=obligation_id,
        control_name=data.control_name,
        control_name_ar=data.control_name_ar,
        control_type=data.control_type,
        description=data.description,
        description_ar=data.description_ar,
        owner=data.owner,
        frequency=data.frequency,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Obligation not found")
    await db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════
# 3. Evidence Expiry Alerts
# ═══════════════════════════════════════════════════════════════════════

@router.get("/alerts/evidence-expiry")
async def get_evidence_expiry_alerts(
    days_ahead: int = Query(30, ge=1, le=365, description="Days ahead to check for expiring evidence"),
    include_expired: bool = Query(True, description="Include already expired evidence"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get evidence expiry alerts.

    Returns expired evidence, soon-to-expire evidence, and summary stats.
    Simple, explainable, operationally useful.
    """
    return await EvidenceExpiryAlertService.get_expiry_alerts(
        db, days_ahead=days_ahead, include_expired=include_expired,
    )


@router.put("/alerts/evidence-expiry/{evidence_id}/renew")
async def renew_evidence_expiry(
    evidence_id: str,
    data: UpdateExpiryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the expiry date of an evidence artifact (e.g., after renewal)."""
    try:
        new_expires = datetime.fromisoformat(data.expires_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format.")

    result = await EvidenceExpiryAlertService.update_evidence_expiry(db, evidence_id, new_expires)
    if not result:
        raise HTTPException(status_code=404, detail="Evidence not found")
    await db.commit()
    return result


@router.post("/alerts/evidence-expiry/auto-mark")
async def auto_mark_expired_evidence(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Automatically mark evidence with past expiry dates as 'expired' status."""
    result = await EvidenceExpiryAlertService.auto_mark_expired(db)
    await db.commit()
    return result
