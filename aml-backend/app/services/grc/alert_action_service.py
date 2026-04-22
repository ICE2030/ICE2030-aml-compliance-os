"""Alert-to-Action conversion service — Phase G3.

Scans for conditions that should generate actions:
- Evidence expiry
- High-risk obligations without controls
- Overdue remediation actions
- Recurring control test failures
- Overdue audit findings

Each generated action is marked with origin='alert_generated'.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.action import GRCAction, ActionPriority, ActionStatus, ActionSourceType, ActionOrigin
from app.models.grc.enterprise_risk import EnterpriseRisk
from app.models.grc.issue import RemediationAction, RemediationStatus
from app.models.grc.audit import (
    AuditFinding, FindingSeverity, FindingStatus,
    ControlTest, TestResult,
)
from app.models.regulatory.obligation import (
    Obligation, Control, EvidenceArtifact, RegulatoryRisk, ObligationControl,
)

logger = logging.getLogger(__name__)


class AlertActionService:
    """Convert system alerts into actionable items."""

    @staticmethod
    async def scan_and_generate(db: AsyncSession) -> dict:
        """Scan all alert conditions and generate actions for unaddressed items."""
        now = datetime.now(timezone.utc)
        generated = []

        # 1. Evidence expiry — evidence expiring within 30 days
        try:
            threshold = now + timedelta(days=30)
            expiring = await db.execute(
                select(EvidenceArtifact).where(
                    EvidenceArtifact.expires_at <= threshold,
                    EvidenceArtifact.expires_at >= now,
                )
            )
            for ev in expiring.scalars().all():
                existing = await db.execute(
                    select(sqla_func.count()).select_from(GRCAction).where(
                        GRCAction.source_type == ActionSourceType.EVIDENCE,
                        GRCAction.source_id == ev.id,
                        GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                    )
                )
                if (existing.scalar() or 0) == 0:
                    action = GRCAction(
                        id=generate_uuid(),
                        title=f"Renew expiring evidence: {ev.name or ev.id}",
                        title_ar=f"تجديد الأدلة المنتهية: {ev.name or ev.id}",
                        description=f"Evidence artifact '{ev.name}' expires on {ev.expires_at.strftime('%Y-%m-%d') if ev.expires_at else 'N/A'}. Renew or replace before expiry.",
                        reason="Evidence expiry detected — compliance gap risk if not renewed.",
                        reason_ar="تم اكتشاف انتهاء صلاحية الأدلة — خطر فجوة الامتثال إذا لم يتم التجديد.",
                        source_type=ActionSourceType.EVIDENCE,
                        source_id=ev.id,
                        source_title=ev.name,
                        origin=ActionOrigin.ALERT_GENERATED,
                        priority=ActionPriority.HIGH,
                        status=ActionStatus.OPEN,
                        due_date=ev.expires_at,
                    )
                    db.add(action)
                    generated.append({"type": "evidence_expiry", "title": action.title, "source_id": ev.id})
        except Exception as e:
            logger.warning(f"Evidence expiry scan failed: {e}")

        # 2. Overdue remediation actions
        try:
            overdue_remediations = await db.execute(
                select(RemediationAction).where(
                    RemediationAction.status.in_([RemediationStatus.NOT_STARTED, RemediationStatus.IN_PROGRESS]),
                    RemediationAction.target_date < now,
                )
            )
            for rem in overdue_remediations.scalars().all():
                existing = await db.execute(
                    select(sqla_func.count()).select_from(GRCAction).where(
                        GRCAction.source_type == ActionSourceType.ISSUE,
                        GRCAction.source_id == rem.id,
                        GRCAction.origin == ActionOrigin.ALERT_GENERATED,
                        GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                    )
                )
                if (existing.scalar() or 0) == 0:
                    action = GRCAction(
                        id=generate_uuid(),
                        title=f"Escalate overdue remediation: {rem.title or rem.id}",
                        title_ar=f"تصعيد الإصلاح المتأخر: {rem.title or rem.id}",
                        description=f"Remediation action '{rem.title}' is past its target date. Escalate to owner.",
                        reason="Overdue remediation — risk of unresolved issue persisting.",
                        reason_ar="إجراء إصلاحي متأخر — خطر استمرار المشكلة دون حل.",
                        source_type=ActionSourceType.ISSUE,
                        source_id=rem.id,
                        source_title=rem.title,
                        origin=ActionOrigin.ALERT_GENERATED,
                        priority=ActionPriority.HIGH,
                        status=ActionStatus.OPEN,
                        due_date=now + timedelta(days=7),
                        owner=rem.owner,
                    )
                    db.add(action)
                    generated.append({"type": "overdue_remediation", "title": action.title, "source_id": rem.id})
        except Exception as e:
            logger.warning(f"Overdue remediation scan failed: {e}")

        # 3. Overdue audit findings
        try:
            overdue_findings = await db.execute(
                select(AuditFinding).where(
                    AuditFinding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION]),
                    AuditFinding.due_date < now,
                )
            )
            for finding in overdue_findings.scalars().all():
                existing = await db.execute(
                    select(sqla_func.count()).select_from(GRCAction).where(
                        GRCAction.source_type == ActionSourceType.AUDIT_FINDING,
                        GRCAction.source_id == finding.id,
                        GRCAction.origin == ActionOrigin.ALERT_GENERATED,
                        GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                    )
                )
                if (existing.scalar() or 0) == 0:
                    prio = ActionPriority.CRITICAL if finding.severity == FindingSeverity.CRITICAL else ActionPriority.HIGH
                    action = GRCAction(
                        id=generate_uuid(),
                        title=f"Address overdue finding: {finding.title}",
                        title_ar=f"معالجة النتيجة المتأخرة: {finding.title_ar or finding.title}",
                        description=f"Audit finding '{finding.title}' is past due date. Severity: {finding.severity.value}.",
                        reason="Overdue audit finding — regulatory exposure if unresolved.",
                        reason_ar="نتيجة تدقيق متأخرة — تعرض تنظيمي إذا لم يتم حلها.",
                        source_type=ActionSourceType.AUDIT_FINDING,
                        source_id=finding.id,
                        source_title=finding.title,
                        origin=ActionOrigin.ALERT_GENERATED,
                        priority=prio,
                        status=ActionStatus.OPEN,
                        due_date=now + timedelta(days=14),
                        owner=finding.owner,
                    )
                    db.add(action)
                    generated.append({"type": "overdue_finding", "title": action.title, "source_id": finding.id})
        except Exception as e:
            logger.warning(f"Overdue findings scan failed: {e}")

        # 4. High-risk obligations without controls
        try:
            high_risk_obls = await db.execute(
                select(RegulatoryRisk).where(
                    RegulatoryRisk.risk_score >= 0.7
                )
            )
            for rr in high_risk_obls.scalars().all():
                # Check if obligation has any controls (via ObligationControl junction)
                control_count = (await db.execute(
                    select(sqla_func.count()).select_from(ObligationControl).where(
                        ObligationControl.obligation_id == rr.obligation_id
                    )
                )).scalar() or 0
                if control_count == 0:
                    existing = await db.execute(
                        select(sqla_func.count()).select_from(GRCAction).where(
                            GRCAction.source_type == ActionSourceType.OBLIGATION,
                            GRCAction.source_id == rr.obligation_id,
                            GRCAction.origin == ActionOrigin.ALERT_GENERATED,
                            GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                        )
                    )
                    if (existing.scalar() or 0) == 0:
                        action = GRCAction(
                            id=generate_uuid(),
                            title=f"Map controls to high-risk obligation: {rr.obligation_id[:20]}...",
                            title_ar=f"ربط ضوابط بالالتزام عالي المخاطر: {rr.obligation_id[:20]}...",
                            description=f"Obligation {rr.obligation_id} has risk score {rr.risk_score:.2f} but no mapped controls.",
                            reason="High-risk obligation with no controls — compliance gap.",
                            reason_ar="التزام عالي المخاطر بدون ضوابط — فجوة امتثال.",
                            source_type=ActionSourceType.OBLIGATION,
                            source_id=rr.obligation_id,
                            origin=ActionOrigin.ALERT_GENERATED,
                            priority=ActionPriority.HIGH,
                            status=ActionStatus.OPEN,
                            due_date=now + timedelta(days=30),
                        )
                        db.add(action)
                        generated.append({"type": "high_risk_no_control", "title": action.title, "source_id": rr.obligation_id})
        except Exception as e:
            logger.warning(f"High-risk obligation scan failed: {e}")

        await db.flush()
        return {
            "scanned_at": now.isoformat(),
            "actions_generated": len(generated),
            "details": generated,
        }
