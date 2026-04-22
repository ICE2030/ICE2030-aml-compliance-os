"""P7 — Export & Reporting service.

Provides:
- Executive report export (JSON)
- Risk register export (CSV)
- Issues export (CSV)
- Actions export (CSV)
- Audit findings export (CSV)
"""
import csv
import io
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.grc.enterprise_risk import EnterpriseRisk
from app.models.grc.issue import Issue, RemediationAction
from app.models.grc.action import GRCAction
from app.models.grc.audit import AuditFinding

logger = logging.getLogger(__name__)


class ExportService:
    """Export GRC data to CSV and JSON formats."""

    @staticmethod
    async def export_risk_register_csv(db: AsyncSession) -> str:
        """Export all enterprise risks as CSV."""
        result = await db.execute(
            select(EnterpriseRisk).order_by(EnterpriseRisk.residual_score.desc())
        )
        risks = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Title", "Title (AR)", "Category", "Business Unit",
            "Inherent Likelihood", "Inherent Impact", "Inherent Score",
            "Residual Likelihood", "Residual Impact", "Residual Score",
            "Treatment Strategy", "Owner", "Status", "Trend",
            "Regulator ID", "Obligation ID", "Created At",
        ])
        for r in risks:
            writer.writerow([
                r.id, r.title, r.title_ar or "", r.category.value,
                r.business_unit or "",
                r.inherent_likelihood.value, r.inherent_impact.value, r.inherent_score,
                r.residual_likelihood.value, r.residual_impact.value, r.residual_score,
                r.treatment_strategy.value, r.owner or "", r.status.value,
                r.trend_direction.value,
                r.regulator_id or "", r.obligation_id or "",
                r.created_at.isoformat() if r.created_at else "",
            ])

        return output.getvalue()

    @staticmethod
    async def export_issues_csv(db: AsyncSession) -> str:
        """Export all issues as CSV."""
        result = await db.execute(
            select(Issue).order_by(Issue.created_at.desc())
        )
        issues = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Title", "Title (AR)", "Source", "Severity", "Status",
            "Escalation Status", "Owner", "Due Date", "Closed At",
            "Risk ID", "Obligation ID", "Control ID", "Created At",
        ])
        for i in issues:
            writer.writerow([
                i.id, i.title, i.title_ar or "", i.source.value,
                i.severity.value, i.status.value, i.escalation_status.value,
                i.owner or "", i.due_date.isoformat() if i.due_date else "",
                i.closed_at.isoformat() if i.closed_at else "",
                i.risk_id or "", i.obligation_id or "", i.control_id or "",
                i.created_at.isoformat() if i.created_at else "",
            ])

        return output.getvalue()

    @staticmethod
    async def export_actions_csv(db: AsyncSession) -> str:
        """Export all GRC actions as CSV."""
        result = await db.execute(
            select(GRCAction).order_by(GRCAction.created_at.desc())
        )
        actions = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Title", "Title (AR)", "Source Type", "Origin",
            "Priority", "Status", "Owner", "Due Date", "Completed At",
            "Resolution Notes", "Created At",
        ])
        for a in actions:
            writer.writerow([
                a.id, a.title, a.title_ar or "", a.source_type.value,
                a.origin.value, a.priority.value, a.status.value,
                a.owner or "", a.due_date.isoformat() if a.due_date else "",
                a.completed_at.isoformat() if a.completed_at else "",
                a.resolution_notes or "",
                a.created_at.isoformat() if a.created_at else "",
            ])

        return output.getvalue()

    @staticmethod
    async def export_findings_csv(db: AsyncSession) -> str:
        """Export all audit findings as CSV."""
        result = await db.execute(
            select(AuditFinding).order_by(AuditFinding.created_at.desc())
        )
        findings = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Engagement ID", "Title", "Title (AR)", "Severity",
            "Status", "Root Cause", "Owner", "Due Date", "Closed At",
            "Created At",
        ])
        for f in findings:
            writer.writerow([
                f.id, f.engagement_id, f.title, f.title_ar or "",
                f.severity.value, f.status.value,
                f.root_cause or "", f.owner or "",
                f.due_date.isoformat() if f.due_date else "",
                f.closed_at.isoformat() if f.closed_at else "",
                f.created_at.isoformat() if f.created_at else "",
            ])

        return output.getvalue()

    @staticmethod
    async def export_executive_report_json(db: AsyncSession) -> dict:
        """Export a full executive report as JSON (includes all dashboard data)."""
        from app.services.grc.grc_dashboard_service import GRCDashboardService
        from app.services.grc.data_integrity_service import DataIntegrityService

        dashboard = await GRCDashboardService.get_executive_summary(db)
        chain_stats = await DataIntegrityService.get_chain_stats(db)

        return {
            "report_type": "executive_grc_report",
            "report_type_ar": "تقرير الحوكمة والمخاطر والامتثال التنفيذي",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dashboard_summary": dashboard,
            "chain_statistics": chain_stats,
        }
