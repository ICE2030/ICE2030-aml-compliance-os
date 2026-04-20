"""Phase 5B API Router: Risk Trend Dashboards + Advanced Pattern Detection."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.regulatory.phase5b_service import (
    ComplianceTrendService, AdvancedPatternService,
)

router = APIRouter(prefix="/api/phase5b", tags=["Phase 5B - Risk Trends & Patterns"])


# ═══════════════════════════════════════════════════════════════════════
# 1. Risk Trend Dashboards
# ═══════════════════════════════════════════════════════════════════════

@router.post("/trends/snapshot")
async def capture_snapshot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Capture a point-in-time snapshot of all compliance indicators.
    
    This is the only way trend data is created — call periodically
    (e.g. daily) to build trend history. No fabricated data.
    """
    result = await ComplianceTrendService.capture_snapshot(db)
    await db.commit()
    return result


@router.get("/trends")
async def get_trends(
    metric_key: Optional[str] = Query(None, description="Filter by specific metric key"),
    limit: int = Query(100, ge=1, le=1000, description="Max data points per metric"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get time-series trend data for compliance indicators.
    
    Returns latest values + historical data points for charting.
    If metric_key is specified, returns only that metric's history.
    """
    return await ComplianceTrendService.get_trends(db, metric_key=metric_key, limit=limit)


@router.get("/trends/metrics")
async def list_metric_keys(
    current_user: User = Depends(get_current_user),
):
    """List all available metric keys for trend tracking."""
    return {
        "metric_keys": ComplianceTrendService.METRIC_KEYS,
        "descriptions": {
            "high_risk_obligations": "Obligations with risk score >= 0.5",
            "unmapped_obligations": "Active obligations not mapped to any control",
            "controls_without_evidence": "Controls with no supporting evidence artifacts",
            "expired_evidence": "Evidence artifacts past their expiry date",
            "expiring_evidence": "Evidence expiring within 30 days",
            "review_backlog": "Obligations pending review",
            "total_obligations": "Total active obligations",
            "total_controls": "Total controls",
            "total_evidence": "Total evidence artifacts",
            "avg_risk_score": "Average risk score across all scored obligations",
            "control_coverage_pct": "Percentage of obligations mapped to controls",
            "evidence_coverage_pct": "Percentage of controls with evidence",
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# 2. Advanced Pattern Detection
# ═══════════════════════════════════════════════════════════════════════

@router.post("/patterns/detect")
async def detect_patterns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run all pattern detection algorithms.
    
    Detects patterns across obligations, controls, evidence gaps,
    and risk concentrations. Previous active patterns are deactivated
    and replaced with fresh results.
    """
    patterns = await AdvancedPatternService.detect_all_patterns(db)
    await db.commit()
    return {
        "patterns_detected": len(patterns),
        "patterns": patterns,
    }


@router.get("/patterns")
async def get_patterns(
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all active compliance patterns, optionally filtered."""
    patterns = await AdvancedPatternService.get_active_patterns(
        db, pattern_type=pattern_type, severity=severity,
    )
    return {
        "count": len(patterns),
        "patterns": patterns,
        "pattern_types": [
            "control_risk_association",
            "persistent_evidence_gap",
            "recurring_control_weakness",
            "obligation_type_risk_cluster",
            "regulator_risk_concentration",
        ],
    }
