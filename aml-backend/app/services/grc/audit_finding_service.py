"""Audit Finding service — CRUD and summary."""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.audit import AuditFinding, AuditEngagement, FindingSeverity, FindingStatus

logger = logging.getLogger(__name__)


class AuditFindingService:
    """Audit finding CRUD."""

    @staticmethod
    async def create_finding(db: AsyncSession, engagement_id: str, data: dict) -> dict:
        result = await db.execute(
            select(AuditEngagement).where(AuditEngagement.id == engagement_id)
        )
        if not result.scalars().first():
            return {"error": "Audit engagement not found"}

        finding = AuditFinding(
            id=generate_uuid(),
            engagement_id=engagement_id,
            title=data["title"],
            title_ar=data.get("title_ar"),
            description=data["description"],
            description_ar=data.get("description_ar"),
            severity=FindingSeverity(data.get("severity", "medium")),
            status=FindingStatus(data.get("status", "open")),
            root_cause=data.get("root_cause"),
            root_cause_ar=data.get("root_cause_ar"),
            control_ids=data.get("control_ids"),
            risk_ids=data.get("risk_ids"),
            obligation_ids=data.get("obligation_ids"),
            evidence_ids=data.get("evidence_ids"),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            due_date=_parse_dt(data.get("due_date")),
            tags=data.get("tags"),
        )
        db.add(finding)
        await db.flush()
        return _finding_to_dict(finding)

    @staticmethod
    async def update_finding(db: AsyncSession, finding_id: str, data: dict) -> dict:
        result = await db.execute(
            select(AuditFinding).where(AuditFinding.id == finding_id)
        )
        finding = result.scalars().first()
        if not finding:
            return {"error": "Audit finding not found"}

        for field in [
            "title", "title_ar", "description", "description_ar",
            "root_cause", "root_cause_ar",
            "control_ids", "risk_ids", "obligation_ids", "evidence_ids",
            "owner", "owner_ar", "tags",
            "closure_evidence", "closure_validated_by",
        ]:
            if field in data:
                setattr(finding, field, data[field])

        if "severity" in data:
            finding.severity = FindingSeverity(data["severity"])
        if "status" in data:
            finding.status = FindingStatus(data["status"])
            if data["status"] == "closed" and not finding.closed_at:
                finding.closed_at = datetime.utcnow()
        if "due_date" in data:
            finding.due_date = _parse_dt(data["due_date"])
        if "closure_validated_at" in data:
            finding.closure_validated_at = _parse_dt(data["closure_validated_at"])

        await db.flush()
        return _finding_to_dict(finding)

    @staticmethod
    async def get_finding(db: AsyncSession, finding_id: str) -> Optional[dict]:
        result = await db.execute(
            select(AuditFinding).where(AuditFinding.id == finding_id)
        )
        finding = result.scalars().first()
        if not finding:
            return None
        return _finding_to_dict(finding)

    @staticmethod
    async def list_findings(
        db: AsyncSession,
        engagement_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        stmt = select(AuditFinding)
        if engagement_id:
            stmt = stmt.where(AuditFinding.engagement_id == engagement_id)
        if severity:
            stmt = stmt.where(AuditFinding.severity == FindingSeverity(severity))
        if status:
            stmt = stmt.where(AuditFinding.status == FindingStatus(status))
        if owner:
            stmt = stmt.where(AuditFinding.owner == owner)

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(AuditFinding.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        findings = result.scalars().all()

        return {
            "items": [_finding_to_dict(f) for f in findings],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_finding(db: AsyncSession, finding_id: str) -> dict:
        result = await db.execute(
            select(AuditFinding).where(AuditFinding.id == finding_id)
        )
        finding = result.scalars().first()
        if not finding:
            return {"error": "Audit finding not found"}
        await db.delete(finding)
        await db.flush()
        return {"deleted": finding_id}

    @staticmethod
    async def get_finding_summary(db: AsyncSession) -> dict:
        total = (await db.execute(
            select(sqla_func.count()).select_from(AuditFinding)
        )).scalar() or 0

        sev_result = await db.execute(
            select(AuditFinding.severity, sqla_func.count())
            .group_by(AuditFinding.severity)
        )
        by_severity = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in sev_result.all()
        }

        status_result = await db.execute(
            select(AuditFinding.status, sqla_func.count())
            .group_by(AuditFinding.status)
        )
        by_status = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in status_result.all()
        }

        open_count = (await db.execute(
            select(sqla_func.count()).select_from(AuditFinding).where(
                AuditFinding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION])
            )
        )).scalar() or 0

        overdue = (await db.execute(
            select(sqla_func.count()).select_from(AuditFinding).where(
                AuditFinding.status.in_([FindingStatus.OPEN, FindingStatus.IN_REMEDIATION]),
                AuditFinding.due_date < datetime.utcnow(),
            )
        )).scalar() or 0

        return {
            "total": total,
            "open": open_count,
            "overdue": overdue,
            "by_severity": by_severity,
            "by_status": by_status,
        }


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _finding_to_dict(f: AuditFinding) -> dict:
    return {
        "id": f.id,
        "engagement_id": f.engagement_id,
        "title": f.title,
        "title_ar": f.title_ar,
        "description": f.description,
        "description_ar": f.description_ar,
        "severity": f.severity.value,
        "status": f.status.value,
        "root_cause": f.root_cause,
        "root_cause_ar": f.root_cause_ar,
        "control_ids": f.control_ids,
        "risk_ids": f.risk_ids,
        "obligation_ids": f.obligation_ids,
        "evidence_ids": f.evidence_ids,
        "owner": f.owner,
        "owner_ar": f.owner_ar,
        "due_date": f.due_date.isoformat() if f.due_date else None,
        "closed_at": f.closed_at.isoformat() if f.closed_at else None,
        "closure_evidence": f.closure_evidence,
        "closure_validated_by": f.closure_validated_by,
        "closure_validated_at": f.closure_validated_at.isoformat() if f.closure_validated_at else None,
        "tags": f.tags,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }
