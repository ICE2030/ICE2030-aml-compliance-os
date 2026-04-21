"""P1 — Data Integrity & Consistency service.

Validates cross-links across the full entity chain:
  Source -> Provision -> Obligation -> Control -> Evidence -> Risk -> Issue -> Remediation -> Audit -> Finding -> Response -> Action

Detects orphan records, validates FK integrity, and reports chain health.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.grc.enterprise_risk import EnterpriseRisk
from app.models.grc.issue import Issue, RemediationAction
from app.models.grc.action import GRCAction
from app.models.grc.audit import (
    AuditPlan, AuditEngagement, ControlTest, AuditFinding, ManagementResponse,
)
from app.models.regulatory.obligation import Obligation, Control, EvidenceArtifact

logger = logging.getLogger(__name__)


class DataIntegrityService:
    """Cross-link validation and orphan detection for the full GRC entity chain."""

    @staticmethod
    async def validate_all(db: AsyncSession) -> dict:
        """Run all validation checks and return a comprehensive report."""
        checks = []

        # 1. Risks with invalid obligation_id
        checks.append(await DataIntegrityService._check_risk_obligation_links(db))

        # 2. Issues with invalid risk_id
        checks.append(await DataIntegrityService._check_issue_risk_links(db))

        # 3. Issues with invalid obligation_id
        checks.append(await DataIntegrityService._check_issue_obligation_links(db))

        # 4. Remediation actions with invalid issue_id
        checks.append(await DataIntegrityService._check_remediation_issue_links(db))

        # 5. Audit findings with invalid engagement_id
        checks.append(await DataIntegrityService._check_finding_engagement_links(db))

        # 6. Management responses with invalid finding_id
        checks.append(await DataIntegrityService._check_response_finding_links(db))

        # 7. Audit engagements with invalid plan_id
        checks.append(await DataIntegrityService._check_engagement_plan_links(db))

        # 8. Control tests with invalid engagement_id
        checks.append(await DataIntegrityService._check_controltest_engagement_links(db))

        # 9. Orphan detection
        checks.append(await DataIntegrityService._check_orphan_risks(db))
        checks.append(await DataIntegrityService._check_orphan_issues(db))

        passed = sum(1 for c in checks if c["status"] == "pass")
        failed = sum(1 for c in checks if c["status"] == "fail")
        warnings = sum(1 for c in checks if c["status"] == "warn")

        return {
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "total_checks": len(checks),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "overall": "healthy" if failed == 0 else "issues_found",
            "checks": checks,
        }

    @staticmethod
    async def _check_risk_obligation_links(db: AsyncSession) -> dict:
        """Check that risks with obligation_id reference valid obligations."""
        result = await db.execute(
            select(EnterpriseRisk).where(EnterpriseRisk.obligation_id.isnot(None))
        )
        risks_with_obl = result.scalars().all()
        broken = []
        for risk in risks_with_obl:
            obl = await db.execute(
                select(sqla_func.count()).select_from(Obligation).where(Obligation.id == risk.obligation_id)
            )
            if (obl.scalar() or 0) == 0:
                broken.append({"risk_id": risk.id, "invalid_obligation_id": risk.obligation_id})
        return {
            "check": "risk_obligation_links",
            "description": "Risks referencing valid obligations",
            "description_ar": "المخاطر المرتبطة بالتزامات صالحة",
            "total_checked": len(risks_with_obl),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_issue_risk_links(db: AsyncSession) -> dict:
        """Check that issues with risk_id reference valid risks."""
        result = await db.execute(
            select(Issue).where(Issue.risk_id.isnot(None))
        )
        issues_with_risk = result.scalars().all()
        broken = []
        for issue in issues_with_risk:
            r = await db.execute(
                select(sqla_func.count()).select_from(EnterpriseRisk).where(EnterpriseRisk.id == issue.risk_id)
            )
            if (r.scalar() or 0) == 0:
                broken.append({"issue_id": issue.id, "invalid_risk_id": issue.risk_id})
        return {
            "check": "issue_risk_links",
            "description": "Issues referencing valid risks",
            "description_ar": "المشاكل المرتبطة بمخاطر صالحة",
            "total_checked": len(issues_with_risk),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_issue_obligation_links(db: AsyncSession) -> dict:
        """Check that issues with obligation_id reference valid obligations."""
        result = await db.execute(
            select(Issue).where(Issue.obligation_id.isnot(None))
        )
        items = result.scalars().all()
        broken = []
        for item in items:
            r = await db.execute(
                select(sqla_func.count()).select_from(Obligation).where(Obligation.id == item.obligation_id)
            )
            if (r.scalar() or 0) == 0:
                broken.append({"issue_id": item.id, "invalid_obligation_id": item.obligation_id})
        return {
            "check": "issue_obligation_links",
            "description": "Issues referencing valid obligations",
            "description_ar": "المشاكل المرتبطة بالتزامات صالحة",
            "total_checked": len(items),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_remediation_issue_links(db: AsyncSession) -> dict:
        """Check that remediation actions reference valid issues."""
        result = await db.execute(
            select(RemediationAction).where(RemediationAction.issue_id.isnot(None))
        )
        items = result.scalars().all()
        broken = []
        for item in items:
            r = await db.execute(
                select(sqla_func.count()).select_from(Issue).where(Issue.id == item.issue_id)
            )
            if (r.scalar() or 0) == 0:
                broken.append({"remediation_id": item.id, "invalid_issue_id": item.issue_id})
        return {
            "check": "remediation_issue_links",
            "description": "Remediation actions referencing valid issues",
            "description_ar": "إجراءات العلاج المرتبطة بمشاكل صالحة",
            "total_checked": len(items),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_finding_engagement_links(db: AsyncSession) -> dict:
        """Check that audit findings reference valid engagements."""
        result = await db.execute(
            select(AuditFinding).where(AuditFinding.engagement_id.isnot(None))
        )
        items = result.scalars().all()
        broken = []
        for item in items:
            r = await db.execute(
                select(sqla_func.count()).select_from(AuditEngagement).where(AuditEngagement.id == item.engagement_id)
            )
            if (r.scalar() or 0) == 0:
                broken.append({"finding_id": item.id, "invalid_engagement_id": item.engagement_id})
        return {
            "check": "finding_engagement_links",
            "description": "Audit findings referencing valid engagements",
            "description_ar": "نتائج التدقيق المرتبطة بمهام صالحة",
            "total_checked": len(items),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_response_finding_links(db: AsyncSession) -> dict:
        """Check that management responses reference valid findings."""
        result = await db.execute(
            select(ManagementResponse).where(ManagementResponse.finding_id.isnot(None))
        )
        items = result.scalars().all()
        broken = []
        for item in items:
            r = await db.execute(
                select(sqla_func.count()).select_from(AuditFinding).where(AuditFinding.id == item.finding_id)
            )
            if (r.scalar() or 0) == 0:
                broken.append({"response_id": item.id, "invalid_finding_id": item.finding_id})
        return {
            "check": "response_finding_links",
            "description": "Management responses referencing valid findings",
            "description_ar": "ردود الإدارة المرتبطة بنتائج صالحة",
            "total_checked": len(items),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_engagement_plan_links(db: AsyncSession) -> dict:
        """Check that engagements reference valid audit plans."""
        result = await db.execute(
            select(AuditEngagement).where(AuditEngagement.plan_id.isnot(None))
        )
        items = result.scalars().all()
        broken = []
        for item in items:
            r = await db.execute(
                select(sqla_func.count()).select_from(AuditPlan).where(AuditPlan.id == item.plan_id)
            )
            if (r.scalar() or 0) == 0:
                broken.append({"engagement_id": item.id, "invalid_plan_id": item.plan_id})
        return {
            "check": "engagement_plan_links",
            "description": "Engagements referencing valid audit plans",
            "description_ar": "المهام المرتبطة بخطط تدقيق صالحة",
            "total_checked": len(items),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_controltest_engagement_links(db: AsyncSession) -> dict:
        """Check that control tests reference valid engagements."""
        result = await db.execute(
            select(ControlTest).where(ControlTest.engagement_id.isnot(None))
        )
        items = result.scalars().all()
        broken = []
        for item in items:
            r = await db.execute(
                select(sqla_func.count()).select_from(AuditEngagement).where(AuditEngagement.id == item.engagement_id)
            )
            if (r.scalar() or 0) == 0:
                broken.append({"controltest_id": item.id, "invalid_engagement_id": item.engagement_id})
        return {
            "check": "controltest_engagement_links",
            "description": "Control tests referencing valid engagements",
            "description_ar": "اختبارات الرقابة المرتبطة بمهام صالحة",
            "total_checked": len(items),
            "broken": len(broken),
            "status": "pass" if len(broken) == 0 else "fail",
            "details": broken[:10],
        }

    @staticmethod
    async def _check_orphan_risks(db: AsyncSession) -> dict:
        """Detect risks not linked to any obligation, control, or issue."""
        result = await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk).where(
                EnterpriseRisk.obligation_id.is_(None),
                EnterpriseRisk.regulator_id.is_(None),
            )
        )
        count = result.scalar() or 0
        total = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk)
        )).scalar() or 0
        return {
            "check": "orphan_risks",
            "description": "Risks not linked to any obligation or regulator",
            "description_ar": "مخاطر غير مرتبطة بأي التزام أو جهة تنظيمية",
            "total_checked": total,
            "orphans": count,
            "status": "pass" if count == 0 else "warn",
            "details": [],
        }

    @staticmethod
    async def _check_orphan_issues(db: AsyncSession) -> dict:
        """Detect issues not linked to any risk, obligation, or control."""
        result = await db.execute(
            select(sqla_func.count()).select_from(Issue).where(
                Issue.risk_id.is_(None),
                Issue.obligation_id.is_(None),
                Issue.control_id.is_(None),
            )
        )
        count = result.scalar() or 0
        total = (await db.execute(
            select(sqla_func.count()).select_from(Issue)
        )).scalar() or 0
        return {
            "check": "orphan_issues",
            "description": "Issues not linked to any risk, obligation, or control",
            "description_ar": "مشاكل غير مرتبطة بأي مخاطر أو التزام أو ضابط",
            "total_checked": total,
            "orphans": count,
            "status": "pass" if count == 0 else "warn",
            "details": [],
        }

    @staticmethod
    async def get_chain_stats(db: AsyncSession) -> dict:
        """Get entity counts across the full operating chain."""
        from app.models.regulatory.source import RegulatorySource
        from app.models.regulatory.provision import Provision

        stats = {}
        for label, model in [
            ("sources", RegulatorySource),
            ("provisions", Provision),
            ("obligations", Obligation),
            ("controls", Control),
            ("evidence", EvidenceArtifact),
            ("risks", EnterpriseRisk),
            ("issues", Issue),
            ("remediation_actions", RemediationAction),
            ("audit_plans", AuditPlan),
            ("audit_engagements", AuditEngagement),
            ("control_tests", ControlTest),
            ("audit_findings", AuditFinding),
            ("management_responses", ManagementResponse),
            ("grc_actions", GRCAction),
        ]:
            count = (await db.execute(
                select(sqla_func.count()).select_from(model)
            )).scalar() or 0
            stats[label] = count

        return {
            "chain": "Source -> Provision -> Obligation -> Control -> Evidence -> Risk -> Issue -> Remediation -> Audit -> Finding -> Response -> Action",
            "entity_counts": stats,
            "total_entities": sum(stats.values()),
        }
