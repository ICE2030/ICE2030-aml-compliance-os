"""GRC Dashboard / Executive Command Center service.

Answers three questions:
1. Where are we exposed?
2. Why are we exposed?
3. What should we do now?

Aggregates data from enterprise risks, issues, remediation actions,
obligations, controls, and evidence to produce a decision-oriented summary.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.grc.enterprise_risk import (
    EnterpriseRisk, RiskCategoryEnum, RiskStatus, TrendDirection,
)
from app.models.grc.issue import (
    Issue, IssueStatus, IssueSeverity, RemediationAction, RemediationStatus,
)
from app.models.regulatory.obligation import (
    Obligation, Control, EvidenceArtifact, RegulatoryRisk,
)

logger = logging.getLogger(__name__)


class GRCDashboardService:
    """Aggregated GRC command center."""

    @staticmethod
    async def get_executive_summary(db: AsyncSession) -> dict:
        """Produce the full executive GRC summary."""

        # ── Risk register summary ──
        total_risks = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk)
        )).scalar() or 0

        high_risks = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk).where(
                EnterpriseRisk.residual_score >= 0.48
            )
        )).scalar() or 0

        deteriorating_risks = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk).where(
                EnterpriseRisk.trend_direction == TrendDirection.DETERIORATING
            )
        )).scalar() or 0

        avg_residual = (await db.execute(
            select(sqla_func.avg(EnterpriseRisk.residual_score))
        )).scalar() or 0

        # ── Issues summary ──
        total_issues = (await db.execute(
            select(sqla_func.count()).select_from(Issue)
        )).scalar() or 0

        open_issues = (await db.execute(
            select(sqla_func.count()).select_from(Issue).where(
                Issue.status.in_([IssueStatus.OPEN, IssueStatus.IN_PROGRESS])
            )
        )).scalar() or 0

        critical_issues = (await db.execute(
            select(sqla_func.count()).select_from(Issue).where(
                Issue.severity == IssueSeverity.CRITICAL,
                Issue.status != IssueStatus.CLOSED,
            )
        )).scalar() or 0

        overdue_issues = (await db.execute(
            select(sqla_func.count()).select_from(Issue).where(
                Issue.status.in_([IssueStatus.OPEN, IssueStatus.IN_PROGRESS]),
                Issue.due_date < datetime.now(timezone.utc),
            )
        )).scalar() or 0

        # ── Remediation summary ──
        total_actions = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction)
        )).scalar() or 0

        blocked_actions = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction).where(
                RemediationAction.status == RemediationStatus.BLOCKED
            )
        )).scalar() or 0

        overdue_actions = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction).where(
                RemediationAction.status.in_([RemediationStatus.NOT_STARTED, RemediationStatus.IN_PROGRESS]),
                RemediationAction.target_date < datetime.now(timezone.utc),
            )
        )).scalar() or 0

        avg_progress = (await db.execute(
            select(sqla_func.avg(RemediationAction.progress_pct))
        )).scalar() or 0

        # ── Regulatory backbone summary ──
        total_obligations = (await db.execute(
            select(sqla_func.count()).select_from(Obligation)
        )).scalar() or 0

        total_controls = (await db.execute(
            select(sqla_func.count()).select_from(Control)
        )).scalar() or 0

        total_evidence = (await db.execute(
            select(sqla_func.count()).select_from(EvidenceArtifact)
        )).scalar() or 0

        # ── Build recommended actions ──
        recommended_actions = []

        if critical_issues > 0:
            recommended_actions.append({
                "priority": "critical",
                "action": f"Address {critical_issues} critical open issue(s) immediately",
                "action_ar": f"معالجة {critical_issues} مشكلة حرجة مفتوحة فوراً",
                "category": "issues",
            })

        if overdue_issues > 0:
            recommended_actions.append({
                "priority": "high",
                "action": f"Resolve {overdue_issues} overdue issue(s) — past due date",
                "action_ar": f"حل {overdue_issues} مشكلة متأخرة — تجاوزت الموعد النهائي",
                "category": "issues",
            })

        if high_risks > 0:
            recommended_actions.append({
                "priority": "high",
                "action": f"Review {high_risks} high-residual-risk item(s) — score ≥ 0.48",
                "action_ar": f"مراجعة {high_risks} عنصر مخاطر متبقية عالية — النتيجة ≥ 0.48",
                "category": "risks",
            })

        if deteriorating_risks > 0:
            recommended_actions.append({
                "priority": "high",
                "action": f"Investigate {deteriorating_risks} risk(s) with deteriorating trend",
                "action_ar": f"التحقيق في {deteriorating_risks} مخاطر ذات اتجاه متدهور",
                "category": "risks",
            })

        if blocked_actions > 0:
            recommended_actions.append({
                "priority": "high",
                "action": f"Unblock {blocked_actions} blocked remediation action(s)",
                "action_ar": f"إزالة العوائق عن {blocked_actions} إجراء علاجي محظور",
                "category": "remediation",
            })

        if overdue_actions > 0:
            recommended_actions.append({
                "priority": "medium",
                "action": f"Follow up on {overdue_actions} overdue remediation action(s)",
                "action_ar": f"متابعة {overdue_actions} إجراء علاجي متأخر",
                "category": "remediation",
            })

        # If no issues at all, suggest proactive review
        if total_risks == 0 and total_issues == 0:
            recommended_actions.append({
                "priority": "low",
                "action": "Create initial enterprise risks and map to regulatory obligations",
                "action_ar": "إنشاء المخاطر المؤسسية الأولية وربطها بالالتزامات التنظيمية",
                "category": "setup",
            })

        # ── Exposure summary (where + why) ──
        exposure_areas = []

        if high_risks > 0:
            # Get top risk categories
            cat_result = await db.execute(
                select(EnterpriseRisk.category, sqla_func.count())
                .where(EnterpriseRisk.residual_score >= 0.48)
                .group_by(EnterpriseRisk.category)
                .order_by(sqla_func.count().desc())
                .limit(3)
            )
            top_cats = [
                {"category": str(row[0].value if hasattr(row[0], "value") else row[0]), "count": row[1]}
                for row in cat_result.all()
            ]
            exposure_areas.append({
                "area": "High Residual Risks",
                "area_ar": "مخاطر متبقية عالية",
                "count": high_risks,
                "details": top_cats,
            })

        if open_issues > 0:
            sev_result = await db.execute(
                select(Issue.severity, sqla_func.count())
                .where(Issue.status.in_([IssueStatus.OPEN, IssueStatus.IN_PROGRESS]))
                .group_by(Issue.severity)
            )
            sev_dist = {
                str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
                for row in sev_result.all()
            }
            exposure_areas.append({
                "area": "Open Issues",
                "area_ar": "المشاكل المفتوحة",
                "count": open_issues,
                "details": sev_dist,
            })

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "risk_register": {
                "total": total_risks,
                "high_risks": high_risks,
                "deteriorating": deteriorating_risks,
                "avg_residual_score": round(float(avg_residual), 4),
            },
            "issues": {
                "total": total_issues,
                "open": open_issues,
                "critical_open": critical_issues,
                "overdue": overdue_issues,
            },
            "remediation": {
                "total": total_actions,
                "blocked": blocked_actions,
                "overdue": overdue_actions,
                "avg_progress_pct": round(float(avg_progress), 1),
            },
            "regulatory_backbone": {
                "obligations": total_obligations,
                "controls": total_controls,
                "evidence": total_evidence,
            },
            "exposure_areas": exposure_areas,
            "recommended_actions": recommended_actions,
            "operating_chain": "Source → Provision → Obligation → Control → Evidence → Risk → Issue → Remediation → Action",
        }
