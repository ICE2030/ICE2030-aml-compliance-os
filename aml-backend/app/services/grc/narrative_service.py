"""Narrative Summary service — rule-based executive summaries.

All narratives are clearly marked as AI-generated, editable, and not authoritative.
Uses rule-based logic (not LLM) to generate summaries from GRC data.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.action import NarrativeSummary, GRCAction, ActionStatus, ActionPriority
from app.models.grc.enterprise_risk import EnterpriseRisk, TrendDirection
from app.models.grc.issue import Issue, IssueStatus, IssueSeverity, RemediationAction, RemediationStatus
from app.models.grc.audit import (
    AuditFinding, FindingSeverity, FindingStatus,
    ControlTest, TestResult,
)

logger = logging.getLogger(__name__)


class NarrativeService:
    """Generate and manage narrative summaries."""

    @staticmethod
    async def generate_executive_summary(db: AsyncSession) -> dict:
        """Generate a rule-based executive summary from current GRC state."""
        now = datetime.now(timezone.utc)

        # Gather stats
        total_risks = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk)
        )).scalar() or 0

        high_risks = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk).where(
                EnterpriseRisk.residual_score >= 0.48
            )
        )).scalar() or 0

        deteriorating = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk).where(
                EnterpriseRisk.trend_direction == TrendDirection.DETERIORATING
            )
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

        open_findings = (await db.execute(
            select(sqla_func.count()).select_from(AuditFinding).where(
                AuditFinding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION])
            )
        )).scalar() or 0

        critical_findings = (await db.execute(
            select(sqla_func.count()).select_from(AuditFinding).where(
                AuditFinding.severity == FindingSeverity.CRITICAL,
                AuditFinding.status != FindingStatus.CLOSED,
            )
        )).scalar() or 0

        ineffective_tests = (await db.execute(
            select(sqla_func.count()).select_from(ControlTest).where(
                ControlTest.overall_result == TestResult.INEFFECTIVE
            )
        )).scalar() or 0

        overdue_remediation = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction).where(
                RemediationAction.status.in_([RemediationStatus.NOT_STARTED, RemediationStatus.IN_PROGRESS]),
                RemediationAction.target_date < now,
            )
        )).scalar() or 0

        open_actions = (await db.execute(
            select(sqla_func.count()).select_from(GRCAction).where(
                GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS])
            )
        )).scalar() or 0

        overdue_actions = (await db.execute(
            select(sqla_func.count()).select_from(GRCAction).where(
                GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                GRCAction.due_date < now,
            )
        )).scalar() or 0

        critical_actions = (await db.execute(
            select(sqla_func.count()).select_from(GRCAction).where(
                GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                GRCAction.priority == ActionPriority.CRITICAL,
            )
        )).scalar() or 0

        # Build narrative sections
        sections = []

        # Risk posture
        if total_risks > 0:
            risk_health = "stable" if high_risks == 0 and deteriorating == 0 else "elevated" if high_risks <= 2 else "critical"
            risk_text = f"The organization maintains {total_risks} enterprise risks in its register."
            risk_text_ar = f"تحتفظ المنظمة بـ {total_risks} مخاطر مؤسسية في سجل المخاطر."
            if high_risks > 0:
                risk_text += f" {high_risks} risk(s) have high residual scores (>= 0.48) requiring management attention."
                risk_text_ar += f" {high_risks} مخاطر لديها درجات متبقية عالية (>= 0.48) تتطلب اهتمام الإدارة."
            if deteriorating > 0:
                risk_text += f" {deteriorating} risk(s) show a deteriorating trend."
                risk_text_ar += f" {deteriorating} مخاطر تظهر اتجاهاً متدهوراً."
            sections.append({"section": "Risk Posture", "section_ar": "وضع المخاطر", "text": risk_text, "text_ar": risk_text_ar, "health": risk_health})

        # Issue & remediation status
        if open_issues > 0 or overdue_remediation > 0:
            issue_health = "critical" if critical_issues > 0 else "elevated" if overdue_remediation > 0 else "manageable"
            issue_text = f"There are {open_issues} open issue(s) across the organization."
            issue_text_ar = f"هناك {open_issues} مشكلة مفتوحة عبر المنظمة."
            if critical_issues > 0:
                issue_text += f" {critical_issues} are critical and require immediate escalation."
                issue_text_ar += f" {critical_issues} منها حرجة وتتطلب تصعيداً فورياً."
            if overdue_remediation > 0:
                issue_text += f" {overdue_remediation} remediation action(s) are overdue."
                issue_text_ar += f" {overdue_remediation} إجراء علاجي متأخر عن الموعد المحدد."
            sections.append({"section": "Issues & Remediation", "section_ar": "المشاكل والإصلاح", "text": issue_text, "text_ar": issue_text_ar, "health": issue_health})

        # Audit posture
        if open_findings > 0 or ineffective_tests > 0:
            audit_health = "critical" if critical_findings > 0 else "elevated" if ineffective_tests > 0 else "manageable"
            audit_text = f"Internal audit has {open_findings} open finding(s)."
            audit_text_ar = f"التدقيق الداخلي لديه {open_findings} نتيجة مفتوحة."
            if critical_findings > 0:
                audit_text += f" {critical_findings} finding(s) are critical severity."
                audit_text_ar += f" {critical_findings} نتيجة ذات خطورة حرجة."
            if ineffective_tests > 0:
                audit_text += f" {ineffective_tests} control test(s) returned ineffective results."
                audit_text_ar += f" {ineffective_tests} اختبار رقابة أعاد نتائج غير فعالة."
            sections.append({"section": "Audit Posture", "section_ar": "وضع التدقيق", "text": audit_text, "text_ar": audit_text_ar, "health": audit_health})

        # Action status
        if open_actions > 0:
            action_health = "critical" if critical_actions > 0 or overdue_actions > 2 else "elevated" if overdue_actions > 0 else "on_track"
            action_text = f"The Action Center has {open_actions} open action(s)."
            action_text_ar = f"مركز الإجراءات لديه {open_actions} إجراء مفتوح."
            if overdue_actions > 0:
                action_text += f" {overdue_actions} action(s) are overdue."
                action_text_ar += f" {overdue_actions} إجراء متأخر."
            if critical_actions > 0:
                action_text += f" {critical_actions} action(s) are critical priority."
                action_text_ar += f" {critical_actions} إجراء ذو أولوية حرجة."
            sections.append({"section": "Action Status", "section_ar": "حالة الإجراءات", "text": action_text, "text_ar": action_text_ar, "health": action_health})

        # Overall health
        overall_health = "critical" if any(s["health"] == "critical" for s in sections) else "elevated" if any(s["health"] == "elevated" for s in sections) else "healthy"

        # Top exposures
        exposures = []
        if high_risks > 0:
            exposures.append({"area": "High Residual Risks", "area_ar": "مخاطر متبقية عالية", "count": high_risks, "severity": "high"})
        if critical_issues > 0:
            exposures.append({"area": "Critical Open Issues", "area_ar": "مشاكل حرجة مفتوحة", "count": critical_issues, "severity": "critical"})
        if critical_findings > 0:
            exposures.append({"area": "Critical Audit Findings", "area_ar": "نتائج تدقيق حرجة", "count": critical_findings, "severity": "critical"})
        if overdue_actions > 0:
            exposures.append({"area": "Overdue Actions", "area_ar": "إجراءات متأخرة", "count": overdue_actions, "severity": "high"})

        # Build full content
        full_content = "EXECUTIVE SUMMARY (AI-Generated — Review Required)\n\n"
        full_content_ar = "الملخص التنفيذي (مُنشأ آلياً — يتطلب مراجعة)\n\n"
        for s in sections:
            full_content += f"**{s['section']}** [{s['health'].upper()}]: {s['text']}\n\n"
            full_content_ar += f"**{s['section_ar']}** [{s['health'].upper()}]: {s['text_ar']}\n\n"

        # Save to DB
        narrative = NarrativeSummary(
            id=generate_uuid(),
            narrative_type="executive",
            content=full_content,
            content_ar=full_content_ar,
            generated_from={
                "total_risks": total_risks,
                "high_risks": high_risks,
                "deteriorating": deteriorating,
                "open_issues": open_issues,
                "critical_issues": critical_issues,
                "open_findings": open_findings,
                "critical_findings": critical_findings,
                "ineffective_tests": ineffective_tests,
                "overdue_remediation": overdue_remediation,
                "open_actions": open_actions,
                "overdue_actions": overdue_actions,
                "critical_actions": critical_actions,
            },
            ai_model="rule-based",
            confidence_note="Generated from current GRC data using rule-based logic. Not authoritative — requires human review.",
        )
        db.add(narrative)
        await db.flush()

        return {
            "id": narrative.id,
            "narrative_type": "executive",
            "overall_health": overall_health,
            "sections": sections,
            "top_exposures": exposures,
            "content": full_content,
            "content_ar": full_content_ar,
            "ai_model": "rule-based",
            "confidence_note": "Generated from current GRC data using rule-based logic. Not authoritative — requires human review.",
            "is_ai_generated": True,
            "is_edited": False,
            "generated_at": now.isoformat(),
            "created_at": narrative.created_at.isoformat() if narrative.created_at else now.isoformat(),
        }

    @staticmethod
    async def update_narrative(db: AsyncSession, narrative_id: str, data: dict) -> dict:
        result = await db.execute(select(NarrativeSummary).where(NarrativeSummary.id == narrative_id))
        narrative = result.scalars().first()
        if not narrative:
            return {"error": "Narrative not found"}

        if "content" in data:
            narrative.content = data["content"]
        if "content_ar" in data:
            narrative.content_ar = data["content_ar"]

        narrative.is_edited = True
        narrative.edited_by = data.get("edited_by")
        narrative.edited_at = datetime.now(timezone.utc)

        await db.flush()
        return _narrative_to_dict(narrative)

    @staticmethod
    async def get_narrative(db: AsyncSession, narrative_id: str) -> Optional[dict]:
        result = await db.execute(select(NarrativeSummary).where(NarrativeSummary.id == narrative_id))
        narrative = result.scalars().first()
        if not narrative:
            return None
        return _narrative_to_dict(narrative)

    @staticmethod
    async def list_narratives(
        db: AsyncSession,
        narrative_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        stmt = select(NarrativeSummary)
        if narrative_type:
            stmt = stmt.where(NarrativeSummary.narrative_type == narrative_type)

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(NarrativeSummary.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        narratives = result.scalars().all()

        return {
            "items": [_narrative_to_dict(n) for n in narratives],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_narrative(db: AsyncSession, narrative_id: str) -> dict:
        result = await db.execute(select(NarrativeSummary).where(NarrativeSummary.id == narrative_id))
        narrative = result.scalars().first()
        if not narrative:
            return {"error": "Narrative not found"}
        await db.delete(narrative)
        await db.flush()
        return {"deleted": narrative_id}


def _narrative_to_dict(n: NarrativeSummary) -> dict:
    return {
        "id": n.id,
        "narrative_type": n.narrative_type,
        "content": n.content,
        "content_ar": n.content_ar,
        "is_edited": n.is_edited,
        "edited_by": n.edited_by,
        "edited_at": n.edited_at.isoformat() if n.edited_at else None,
        "generated_from": n.generated_from,
        "ai_model": n.ai_model,
        "confidence_note": n.confidence_note,
        "is_ai_generated": True,
        "tags": n.tags,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }
