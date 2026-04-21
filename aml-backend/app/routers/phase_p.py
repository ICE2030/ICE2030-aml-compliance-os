"""Phase P — Productization & Hardening API endpoints.

P1: Data Integrity validation
P2: GRC Audit Trail (prev/new values)
P3: RBAC-protected endpoints
P4: Dashboard Trustworthiness validation
P7: Export & Reporting (CSV, JSON)
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sqla_func
from app.core.database import get_db
from app.core.auth import get_current_user, require_roles
from app.models.user import User, UserRole
from app.services.grc.data_integrity_service import DataIntegrityService
from app.services.grc.grc_audit_service import GRCAuditService
from app.services.grc.export_service import ExportService
from app.services.grc.grc_dashboard_service import GRCDashboardService
from app.services.grc.performance_service import PerformanceService
from app.models.grc.enterprise_risk import EnterpriseRisk
from app.models.grc.issue import Issue, IssueStatus, RemediationAction
from app.models.grc.audit import AuditFinding, FindingStatus, AuditEngagement
from app.models.grc.action import GRCAction, ActionStatus
import io

router = APIRouter(prefix="/api/grc/admin", tags=["GRC - Admin & Hardening"])


# ── P1: Data Integrity ──

@router.get("/integrity/validate")
async def validate_data_integrity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER)),
):
    """Run full cross-link validation across the GRC entity chain."""
    return await DataIntegrityService.validate_all(db)


@router.get("/integrity/chain-stats")
async def get_chain_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER)),
):
    """Get entity counts across the full operating chain."""
    return await DataIntegrityService.get_chain_stats(db)


# ── P2: GRC Audit Trail ──

@router.get("/audit-trail")
async def get_grc_audit_trail(
    resource_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER)),
):
    """Get recent GRC entity changes with prev/new values."""
    return await GRCAuditService.get_recent_changes(db, resource_type=resource_type, limit=limit)


@router.get("/audit-trail/{resource_type}/{resource_id}")
async def get_entity_audit_history(
    resource_type: str,
    resource_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER)),
):
    """Get audit history for a specific GRC entity."""
    return await GRCAuditService.get_entity_history(db, resource_type, resource_id, limit=limit)


# ── P7: Export & Reporting ──

@router.get("/export/risks/csv")
async def export_risks_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST)),
):
    """Export risk register as CSV."""
    csv_data = await ExportService.export_risk_register_csv(db)
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=risk_register.csv"},
    )


@router.get("/export/issues/csv")
async def export_issues_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST)),
):
    """Export issues as CSV."""
    csv_data = await ExportService.export_issues_csv(db)
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=issues.csv"},
    )


@router.get("/export/actions/csv")
async def export_actions_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST)),
):
    """Export GRC actions as CSV."""
    csv_data = await ExportService.export_actions_csv(db)
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=actions.csv"},
    )


@router.get("/export/findings/csv")
async def export_findings_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER)),
):
    """Export audit findings as CSV."""
    csv_data = await ExportService.export_findings_csv(db)
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_findings.csv"},
    )


@router.get("/export/executive-report")
async def export_executive_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER)),
):
    """Export executive GRC report as JSON."""
    return await ExportService.export_executive_report_json(db)


# ── P3: RBAC Info ──

@router.get("/rbac/permissions")
async def get_rbac_permissions(
    current_user: User = Depends(get_current_user),
):
    """Get current user's role and permissions matrix."""
    permissions = _get_role_permissions(current_user.role)
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.value,
        "permissions": permissions,
    }


@router.get("/rbac/matrix")
async def get_rbac_matrix(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Get full RBAC permissions matrix (admin only)."""
    matrix = {}
    for role in UserRole:
        matrix[role.value] = _get_role_permissions(role)
    return {"roles": matrix}


def _get_role_permissions(role: UserRole) -> dict:
    """Define per-module read/write permissions for each role."""
    # Permission matrix: module -> {read, write}
    all_modules = [
        "risks", "issues", "remediation", "actions",
        "audit_plans", "audit_engagements", "control_tests",
        "audit_findings", "management_responses",
        "narratives", "cross_links", "dashboard",
        "data_integrity", "audit_trail", "exports",
    ]

    if role == UserRole.ADMIN:
        return {m: {"read": True, "write": True} for m in all_modules}

    if role == UserRole.COMPLIANCE_OFFICER:
        perms = {m: {"read": True, "write": True} for m in all_modules}
        perms["audit_plans"]["write"] = False
        perms["audit_engagements"]["write"] = False
        return perms

    if role == UserRole.ANALYST:
        perms = {m: {"read": True, "write": False} for m in all_modules}
        perms["risks"]["write"] = True
        perms["issues"]["write"] = True
        perms["remediation"]["write"] = True
        perms["actions"]["write"] = True
        perms["data_integrity"]["read"] = False
        perms["audit_trail"]["read"] = False
        return perms

    if role == UserRole.AUDITOR:
        perms = {m: {"read": True, "write": False} for m in all_modules}
        perms["audit_plans"]["write"] = True
        perms["audit_engagements"]["write"] = True
        perms["control_tests"]["write"] = True
        perms["audit_findings"]["write"] = True
        perms["management_responses"]["write"] = True
        perms["audit_trail"]["read"] = True
        return perms

    # VIEWER — read only
    perms = {m: {"read": True, "write": False} for m in all_modules}
    perms["data_integrity"]["read"] = False
    perms["audit_trail"]["read"] = False
    perms["exports"]["read"] = False
    return perms


# ── P4: Dashboard Trustworthiness Validation ──

@router.get("/dashboard/validate")
async def validate_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER)),
):
    """Validate all dashboard metrics match underlying DB queries.

    Compares each dashboard metric against an independent DB count
    to ensure no hardcoded or approximated values.
    """
    # Get dashboard data
    dashboard = await GRCDashboardService.get_executive_summary(db)

    # Independent verification queries
    checks = []

    # Risk counts
    actual_risks = (await db.execute(
        select(sqla_func.count()).select_from(EnterpriseRisk)
    )).scalar() or 0
    checks.append({
        "metric": "risk_register.total",
        "dashboard_value": dashboard["risk_register"]["total"],
        "db_value": actual_risks,
        "match": dashboard["risk_register"]["total"] == actual_risks,
    })

    # Issue counts
    actual_issues = (await db.execute(
        select(sqla_func.count()).select_from(Issue)
    )).scalar() or 0
    checks.append({
        "metric": "issues.total",
        "dashboard_value": dashboard["issues"]["total"],
        "db_value": actual_issues,
        "match": dashboard["issues"]["total"] == actual_issues,
    })

    actual_open_issues = (await db.execute(
        select(sqla_func.count()).select_from(Issue).where(
            Issue.status.in_([IssueStatus.OPEN, IssueStatus.IN_PROGRESS])
        )
    )).scalar() or 0
    checks.append({
        "metric": "issues.open",
        "dashboard_value": dashboard["issues"]["open"],
        "db_value": actual_open_issues,
        "match": dashboard["issues"]["open"] == actual_open_issues,
    })

    # Remediation counts
    actual_remediations = (await db.execute(
        select(sqla_func.count()).select_from(RemediationAction)
    )).scalar() or 0
    checks.append({
        "metric": "remediation.total",
        "dashboard_value": dashboard["remediation"]["total"],
        "db_value": actual_remediations,
        "match": dashboard["remediation"]["total"] == actual_remediations,
    })

    # Audit finding counts
    actual_findings = (await db.execute(
        select(sqla_func.count()).select_from(AuditFinding)
    )).scalar() or 0
    checks.append({
        "metric": "audit.total_findings",
        "dashboard_value": dashboard["audit"]["total_findings"],
        "db_value": actual_findings,
        "match": dashboard["audit"]["total_findings"] == actual_findings,
    })

    actual_open_findings = (await db.execute(
        select(sqla_func.count()).select_from(AuditFinding).where(
            AuditFinding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION])
        )
    )).scalar() or 0
    checks.append({
        "metric": "audit.open_findings",
        "dashboard_value": dashboard["audit"]["open_findings"],
        "db_value": actual_open_findings,
        "match": dashboard["audit"]["open_findings"] == actual_open_findings,
    })

    # Action center counts
    actual_actions = (await db.execute(
        select(sqla_func.count()).select_from(GRCAction)
    )).scalar() or 0
    action_center = dashboard.get("action_center", {})
    checks.append({
        "metric": "action_center.total",
        "dashboard_value": action_center.get("total", 0),
        "db_value": actual_actions,
        "match": action_center.get("total", 0) == actual_actions,
    })

    actual_open_actions = (await db.execute(
        select(sqla_func.count()).select_from(GRCAction).where(
            GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS])
        )
    )).scalar() or 0
    checks.append({
        "metric": "action_center.open",
        "dashboard_value": action_center.get("open", 0),
        "db_value": actual_open_actions,
        "match": action_center.get("open", 0) == actual_open_actions,
    })

    passed = sum(1 for c in checks if c["match"])
    failed = len(checks) - passed

    return {
        "validated_at": dashboard["generated_at"],
        "total_checks": len(checks),
        "passed": passed,
        "failed": failed,
        "trustworthy": failed == 0,
        "checks": checks,
    }


# ── P6: Performance & Scalability ──

@router.post("/performance/ensure-indexes")
async def ensure_indexes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Create recommended database indexes for GRC queries. Safe to call repeatedly."""
    return await PerformanceService.ensure_indexes(db)


@router.get("/performance/stats")
async def get_performance_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Get table statistics and PostgreSQL migration readiness report."""
    return await PerformanceService.get_query_stats(db)
