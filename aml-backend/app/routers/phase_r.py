"""Phase R: Regulatory Data Maturity Layer — API endpoints.

Endpoints:
1. Change Detection — create baselines, detect changes, view history
2. Impact Propagation — propagate impacts, view/resolve impacts
3. Alerting — view/acknowledge/resolve/dismiss alerts
4. Freshness — compute freshness, view dashboard
5. Version Comparison — compare provision versions, document diffs
6. Orchestrator — run full pipeline
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.regulatory.phase_r_service import (
    ChangeDetectionService,
    ImpactPropagationService,
    AlertingService,
    FreshnessService,
    VersionComparisonService,
    PhaseROrchestrator,
)

router = APIRouter(prefix="/api/phase-r", tags=["Phase R: Regulatory Maturity"])


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/pipeline/run")
async def run_full_pipeline(
    regulator_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the full Phase R pipeline: baseline → detect → propagate → alert → freshness."""
    result = await PhaseROrchestrator.run_full_pipeline(db, regulator_id=regulator_id)
    await db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Change Detection
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/changes/baseline")
async def create_baseline_snapshots(
    regulator_id: Optional[str] = None,
    document_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create baseline provision snapshots for future change detection."""
    result = await ChangeDetectionService.create_baseline_snapshots(
        db, regulator_id=regulator_id, document_id=document_id
    )
    await db.commit()
    return result


@router.post("/changes/detect")
async def detect_changes(
    regulator_id: Optional[str] = None,
    document_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect provision changes by comparing against baseline snapshots."""
    result = await ChangeDetectionService.detect_changes(
        db, regulator_id=regulator_id, document_id=document_id
    )
    await db.commit()
    return result


@router.post("/changes/detect-documents")
async def detect_document_changes(
    regulator_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect new/removed documents for a regulator."""
    result = await ChangeDetectionService.detect_document_changes(db, regulator_id)
    return result


@router.get("/changes/history")
async def get_change_history(
    regulator_id: Optional[str] = None,
    document_id: Optional[str] = None,
    classification: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get change history with optional filtering."""
    return await ChangeDetectionService.get_change_history(
        db,
        regulator_id=regulator_id,
        document_id=document_id,
        classification=classification,
        limit=limit,
        offset=offset,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Impact Propagation
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/impacts/propagate/{change_id}")
async def propagate_change(
    change_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Propagate a single regulatory change to downstream records."""
    result = await ImpactPropagationService.propagate_change(db, change_id)
    await db.commit()
    return result


@router.post("/impacts/propagate-all")
async def propagate_all_pending(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Propagate all pending changes that haven't been propagated yet."""
    result = await ImpactPropagationService.propagate_all_pending(db)
    await db.commit()
    return result


@router.get("/impacts")
async def get_impacts(
    change_id: Optional[str] = None,
    impact_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get impact records with optional filtering."""
    return await ImpactPropagationService.get_impacts(
        db,
        change_id=change_id,
        impact_type=impact_type,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/impacts/{impact_id}/resolve")
async def resolve_impact(
    impact_id: str,
    status: str = "reviewed",
    resolved_by: str = "system",
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve an impact record."""
    result = await ImpactPropagationService.resolve_impact(
        db, impact_id, status=status, resolved_by=resolved_by, notes=notes
    )
    await db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Alerting
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/alerts")
async def get_alerts(
    regulator_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get regulatory alerts with optional filtering."""
    return await AlertingService.get_alerts(
        db,
        regulator_id=regulator_id,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = "system",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge a regulatory alert."""
    result = await AlertingService.acknowledge_alert(db, alert_id, acknowledged_by)
    await db.commit()
    return result


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve a regulatory alert."""
    result = await AlertingService.resolve_alert(db, alert_id)
    await db.commit()
    return result


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dismiss a regulatory alert."""
    result = await AlertingService.dismiss_alert(db, alert_id)
    await db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Freshness
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/freshness/compute")
async def compute_freshness(
    regulator_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute freshness for a specific regulator or all regulators."""
    if regulator_id:
        result = await FreshnessService.compute_freshness(db, regulator_id)
    else:
        result = await FreshnessService.compute_all_freshness(db)
    await db.commit()
    return result


@router.get("/freshness/dashboard")
async def freshness_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get freshness dashboard for all regulators."""
    return await FreshnessService.get_freshness_dashboard(db)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Version Comparison
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/versions/provision/{provision_id}")
async def compare_provision_versions(
    provision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all versions of a provision with diffs between each version."""
    return await VersionComparisonService.compare_provision_versions(db, provision_id)


@router.get("/versions/document/{document_id}")
async def compare_document_versions(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare all provision changes within a document."""
    return await VersionComparisonService.compare_document_versions(db, document_id)


@router.get("/versions/provision/{provision_id}/at/{version_number}")
async def get_provision_at_version(
    provision_id: str,
    version_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific version of a provision."""
    result = await VersionComparisonService.get_provision_at_version(
        db, provision_id, version_number
    )
    if not result:
        return {"error": "Version not found"}
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Documents listing (for version comparison UI)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/documents")
async def list_documents(
    regulator_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List regulatory documents for version comparison."""
    from app.models.regulatory.source import RegulatoryDocument
    stmt = select(RegulatoryDocument)
    if regulator_id:
        stmt = stmt.where(RegulatoryDocument.regulator_id == regulator_id)
    stmt = stmt.order_by(RegulatoryDocument.title)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "title_ar": d.title_ar,
            "document_type": d.document_type,
            "regulator_id": d.regulator_id,
            "status": d.status.value if hasattr(d.status, "value") else str(d.status),
        }
        for d in docs
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard / Summary
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def phase_r_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get Phase R summary dashboard."""
    from sqlalchemy import func as sqla_func
    from app.models.regulatory.phase_r import (
        ProvisionSnapshot, RegulatoryChange, ImpactRecord,
        RegulatoryAlert, RegulatorFreshness,
        AlertStatus, ImpactStatus,
    )

    # Counts
    snapshots_count = (await db.execute(
        select(sqla_func.count()).select_from(ProvisionSnapshot)
    )).scalar() or 0

    changes_count = (await db.execute(
        select(sqla_func.count()).select_from(RegulatoryChange)
    )).scalar() or 0

    impacts_count = (await db.execute(
        select(sqla_func.count()).select_from(ImpactRecord)
    )).scalar() or 0

    pending_impacts = (await db.execute(
        select(sqla_func.count()).select_from(ImpactRecord).where(
            ImpactRecord.status == ImpactStatus.REQUIRES_REVIEW
        )
    )).scalar() or 0

    active_alerts = (await db.execute(
        select(sqla_func.count()).select_from(RegulatoryAlert).where(
            RegulatoryAlert.status == AlertStatus.ACTIVE
        )
    )).scalar() or 0

    total_alerts = (await db.execute(
        select(sqla_func.count()).select_from(RegulatoryAlert)
    )).scalar() or 0

    # Freshness summary
    freshness_result = await db.execute(
        select(RegulatorFreshness).order_by(RegulatorFreshness.confidence_score.asc())
    )
    freshness_records = list(freshness_result.scalars().all())

    lowest_confidence = None
    if freshness_records:
        lowest_confidence = {
            "regulator_id": freshness_records[0].regulator_id,
            "confidence_score": freshness_records[0].confidence_score,
            "freshness_status": freshness_records[0].freshness_status.value if hasattr(freshness_records[0].freshness_status, "value") else str(freshness_records[0].freshness_status),
        }

    # Change classification breakdown
    class_result = await db.execute(
        select(
            RegulatoryChange.classification,
            sqla_func.count()
        ).group_by(RegulatoryChange.classification)
    )
    classification_breakdown = {
        str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
        for row in class_result.all()
    }

    return {
        "snapshots": snapshots_count,
        "changes": {
            "total": changes_count,
            "by_classification": classification_breakdown,
        },
        "impacts": {
            "total": impacts_count,
            "pending_review": pending_impacts,
        },
        "alerts": {
            "total": total_alerts,
            "active": active_alerts,
        },
        "freshness": {
            "regulators_tracked": len(freshness_records),
            "lowest_confidence": lowest_confidence,
        },
    }
