"""Phase 4 API Router: Control Mapping, Evidence, Risk Scoring, Gap Analysis, Executive Reporting."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.regulatory.phase4_service import (
    ControlMappingService, EvidenceMappingService,
    RiskScoringService, GapAnalysisService, ExecutiveReportingService,
)

router = APIRouter(prefix="/api/phase4", tags=["Phase 4 - Controls, Evidence, Risk"])


# ═══════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════

class ControlCreate(BaseModel):
    name: str
    control_type: str  # policy, procedure, technical, monitoring, training
    description: Optional[str] = None
    name_ar: Optional[str] = None
    description_ar: Optional[str] = None
    owner: Optional[str] = None
    frequency: Optional[str] = None
    status: str = "draft"
    regulator_id: Optional[str] = None
    source_id: Optional[str] = None

class ControlUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    control_type: Optional[str] = None
    owner: Optional[str] = None
    frequency: Optional[str] = None
    status: Optional[str] = None
    regulator_id: Optional[str] = None
    source_id: Optional[str] = None

class ObligationMapping(BaseModel):
    obligation_id: str
    mapping_confidence: float = 1.0
    mapping_method: str = "manual"
    notes: Optional[str] = None

class EvidenceCreate(BaseModel):
    control_id: str
    name: str
    artifact_type: str  # document, log, attestation, report, etc.
    description: Optional[str] = None
    name_ar: Optional[str] = None
    description_ar: Optional[str] = None
    source_system: Optional[str] = None
    collection_method: Optional[str] = None
    periodicity: Optional[str] = None
    owner: Optional[str] = None
    status: str = "active"

class EvidenceUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    artifact_type: Optional[str] = None
    source_system: Optional[str] = None
    collection_method: Optional[str] = None
    periodicity: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# 1. Control CRUD + Mapping
# ═══════════════════════════════════════════════════════════════════════

@router.post("/controls")
async def create_control(data: ControlCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    control = await ControlMappingService.create_control(
        db, name=data.name, control_type=data.control_type,
        description=data.description, name_ar=data.name_ar,
        description_ar=data.description_ar, owner=data.owner,
        frequency=data.frequency, status=data.status,
        regulator_id=data.regulator_id, source_id=data.source_id,
    )
    await db.commit()
    return await ControlMappingService.get_control(db, control.id)


@router.get("/controls")
async def list_controls(
    control_type: Optional[str] = None,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await ControlMappingService.list_controls(
        db, control_type=control_type, status=status, owner=owner, skip=skip, limit=limit,
    )
    return {"items": items, "total": total}


@router.get("/controls/{control_id}")
async def get_control(control_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await ControlMappingService.get_control(db, control_id)
    if not result:
        raise HTTPException(status_code=404, detail="Control not found")
    return result


@router.put("/controls/{control_id}")
async def update_control(control_id: str, data: ControlUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    update_data = data.model_dump(exclude_none=True)
    control = await ControlMappingService.update_control(db, control_id, **update_data)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    await db.commit()
    return await ControlMappingService.get_control(db, control.id)


@router.delete("/controls/{control_id}")
async def delete_control(control_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    deleted = await ControlMappingService.delete_control(db, control_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Control not found")
    await db.commit()
    return {"deleted": True}


@router.post("/controls/{control_id}/map-obligation")
async def map_obligation(control_id: str, data: ObligationMapping, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await ControlMappingService.map_obligation_to_control(
        db, obligation_id=data.obligation_id, control_id=control_id,
        mapping_confidence=data.mapping_confidence,
        mapping_method=data.mapping_method, notes=data.notes,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Obligation or control not found")
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    await db.commit()
    return result


@router.delete("/controls/{control_id}/unmap-obligation/{obligation_id}")
async def unmap_obligation(control_id: str, obligation_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    removed = await ControlMappingService.unmap_obligation_from_control(db, obligation_id, control_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.commit()
    return {"unmapped": True}


@router.get("/controls/{control_id}/obligations")
async def get_control_obligations(control_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await ControlMappingService.get_control_obligations(db, control_id)


# ═══════════════════════════════════════════════════════════════════════
# 2. Evidence CRUD + Chain
# ═══════════════════════════════════════════════════════════════════════

@router.post("/evidence")
async def create_evidence(data: EvidenceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ev = await EvidenceMappingService.create_evidence(
        db, control_id=data.control_id, name=data.name,
        artifact_type=data.artifact_type, description=data.description,
        name_ar=data.name_ar, description_ar=data.description_ar,
        source_system=data.source_system, collection_method=data.collection_method,
        periodicity=data.periodicity, owner=data.owner, status=data.status,
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Control not found")
    await db.commit()
    return EvidenceMappingService._serialize_evidence(ev)


@router.get("/evidence")
async def list_evidence(
    control_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await EvidenceMappingService.list_evidence(
        db, control_id=control_id, artifact_type=artifact_type,
        status=status, skip=skip, limit=limit,
    )
    return {"items": items, "total": total}


@router.get("/evidence/{evidence_id}")
async def get_evidence(evidence_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await EvidenceMappingService.get_evidence(db, evidence_id)
    if not result:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return result


@router.put("/evidence/{evidence_id}")
async def update_evidence(evidence_id: str, data: EvidenceUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    update_data = data.model_dump(exclude_none=True)
    ev = await EvidenceMappingService.update_evidence(db, evidence_id, **update_data)
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    await db.commit()
    return EvidenceMappingService._serialize_evidence(ev)


@router.delete("/evidence/{evidence_id}")
async def delete_evidence(evidence_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    deleted = await EvidenceMappingService.delete_evidence(db, evidence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence not found")
    await db.commit()
    return {"deleted": True}


@router.get("/evidence/{evidence_id}/chain")
async def get_evidence_chain(evidence_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Full provenance chain: Evidence -> Control -> Obligation -> Provision -> Source."""
    chain = await EvidenceMappingService.get_evidence_chain(db, evidence_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return chain


# ═══════════════════════════════════════════════════════════════════════
# 3. Risk Scoring
# ═══════════════════════════════════════════════════════════════════════

@router.post("/risks/score-all")
async def score_all_obligations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Score all active obligations and persist risk records."""
    scores = await RiskScoringService.score_all_obligations(db)
    await db.commit()
    return {"scored": len(scores), "scores": scores}


@router.get("/risks/summary")
async def get_risk_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await RiskScoringService.get_risk_summary(db)


@router.get("/risks/{obligation_id}")
async def get_obligation_risk(obligation_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get explainable risk score for a single obligation."""
    result = await RiskScoringService.score_obligation(db, obligation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return result


# ═══════════════════════════════════════════════════════════════════════
# 4. Gap Analysis
# ═══════════════════════════════════════════════════════════════════════

@router.get("/gaps")
async def run_gap_analysis(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Full gap analysis: unmapped obligations, missing evidence, high-risk items."""
    return await GapAnalysisService.run_full_analysis(db)


@router.get("/gaps/unmapped-obligations")
async def get_unmapped_obligations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await GapAnalysisService.obligations_without_controls(db)


@router.get("/gaps/controls-without-evidence")
async def get_controls_without_evidence(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await GapAnalysisService.controls_without_evidence(db)


@router.get("/gaps/high-risk")
async def get_high_risk_obligations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await GapAnalysisService.high_risk_obligations(db)


@router.get("/gaps/needs-review")
async def get_obligations_needing_review(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await GapAnalysisService.obligations_needing_review(db)


# ═══════════════════════════════════════════════════════════════════════
# 5. Executive Reporting
# ═══════════════════════════════════════════════════════════════════════

@router.get("/reports/executive")
async def get_executive_report(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Board-ready executive compliance report."""
    return await ExecutiveReportingService.generate_executive_report(db)


# ═══════════════════════════════════════════════════════════════════════
# 6. Seed Phase 4 Data
# ═══════════════════════════════════════════════════════════════════════

@router.post("/seed")
async def seed_phase4_data(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Seed sample controls, evidence, and mappings for demonstration."""
    from app.services.regulatory.phase4_seed_service import Phase4SeedService
    result = await Phase4SeedService.seed_all(db)
    await db.commit()
    return result
