"""Issue Management service.

Handles:
- Issue CRUD with lifecycle tracking
- Issue aging calculation
- Links to risks, controls, obligations, regulators
- Severity distribution and statistics
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.issue import (
    Issue, IssueSource, IssueSeverity, IssueStatus, EscalationStatus,
)

logger = logging.getLogger(__name__)


def _compute_aging_days(issue: Issue) -> int:
    """Compute days since issue was created (or until closure)."""
    now = datetime.now(timezone.utc)
    end = issue.closed_at or now
    # Normalize to aware UTC for safe subtraction (SQLite may mix naive/aware)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = issue.created_at
    if start:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return max(0, (end - start).days)
    return 0


class IssueManagementService:
    """Issue lifecycle management."""

    @staticmethod
    async def create_issue(db: AsyncSession, data: dict) -> dict:
        """Create a new issue."""
        issue = Issue(
            id=generate_uuid(),
            title=data["title"],
            title_ar=data.get("title_ar"),
            description=data["description"],
            description_ar=data.get("description_ar"),
            source=IssueSource(data.get("source", "compliance")),
            severity=IssueSeverity(data.get("severity", "medium")),
            status=IssueStatus(data.get("status", "open")),
            escalation_status=EscalationStatus(data.get("escalation_status", "none")),
            risk_id=data.get("risk_id"),
            control_id=data.get("control_id"),
            obligation_id=data.get("obligation_id"),
            regulator_id=data.get("regulator_id"),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            tags=data.get("tags"),
        )
        if data.get("due_date"):
            issue.due_date = datetime.fromisoformat(data["due_date"])

        db.add(issue)
        await db.flush()
        return _issue_to_dict(issue)

    @staticmethod
    async def update_issue(db: AsyncSession, issue_id: str, data: dict) -> dict:
        """Update an issue."""
        result = await db.execute(
            select(Issue).where(Issue.id == issue_id)
        )
        issue = result.scalars().first()
        if not issue:
            return {"error": "Issue not found"}

        for field in [
            "title", "title_ar", "description", "description_ar",
            "owner", "owner_ar", "closure_evidence",
            "closure_validated_by", "tags",
            "risk_id", "control_id", "obligation_id", "regulator_id",
        ]:
            if field in data:
                setattr(issue, field, data[field])

        if "source" in data:
            issue.source = IssueSource(data["source"])
        if "severity" in data:
            issue.severity = IssueSeverity(data["severity"])
        if "status" in data:
            new_status = IssueStatus(data["status"])
            if new_status == IssueStatus.CLOSED and issue.status != IssueStatus.CLOSED:
                issue.closed_at = datetime.now(timezone.utc)
            issue.status = new_status
        if "escalation_status" in data:
            issue.escalation_status = EscalationStatus(data["escalation_status"])
        if "due_date" in data and data["due_date"]:
            issue.due_date = datetime.fromisoformat(data["due_date"])
        if "closure_validated_at" in data and data["closure_validated_at"]:
            issue.closure_validated_at = datetime.fromisoformat(data["closure_validated_at"])

        await db.flush()
        return _issue_to_dict(issue)

    @staticmethod
    async def get_issue(db: AsyncSession, issue_id: str) -> Optional[dict]:
        """Get a single issue by ID."""
        result = await db.execute(
            select(Issue).where(Issue.id == issue_id)
        )
        issue = result.scalars().first()
        if not issue:
            return None
        return _issue_to_dict(issue)

    @staticmethod
    async def list_issues(
        db: AsyncSession,
        source: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        risk_id: Optional[str] = None,
        obligation_id: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List issues with filtering."""
        stmt = select(Issue)

        if source:
            stmt = stmt.where(Issue.source == IssueSource(source))
        if severity:
            stmt = stmt.where(Issue.severity == IssueSeverity(severity))
        if status:
            stmt = stmt.where(Issue.status == IssueStatus(status))
        if risk_id:
            stmt = stmt.where(Issue.risk_id == risk_id)
        if obligation_id:
            stmt = stmt.where(Issue.obligation_id == obligation_id)
        if owner:
            stmt = stmt.where(Issue.owner == owner)

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Issue.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        issues = result.scalars().all()

        return {
            "items": [_issue_to_dict(i) for i in issues],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_issue(db: AsyncSession, issue_id: str) -> dict:
        """Delete an issue."""
        result = await db.execute(
            select(Issue).where(Issue.id == issue_id)
        )
        issue = result.scalars().first()
        if not issue:
            return {"error": "Issue not found"}
        await db.delete(issue)
        await db.flush()
        return {"deleted": issue_id}

    @staticmethod
    async def get_issue_summary(db: AsyncSession) -> dict:
        """Get summary stats for issue management."""
        total = (await db.execute(
            select(sqla_func.count()).select_from(Issue)
        )).scalar() or 0

        open_count = (await db.execute(
            select(sqla_func.count()).select_from(Issue).where(
                Issue.status.in_([IssueStatus.OPEN, IssueStatus.IN_PROGRESS])
            )
        )).scalar() or 0

        overdue_count = (await db.execute(
            select(sqla_func.count()).select_from(Issue).where(
                Issue.status.in_([IssueStatus.OPEN, IssueStatus.IN_PROGRESS]),
                Issue.due_date < datetime.now(timezone.utc),
            )
        )).scalar() or 0

        critical_count = (await db.execute(
            select(sqla_func.count()).select_from(Issue).where(
                Issue.severity == IssueSeverity.CRITICAL,
                Issue.status != IssueStatus.CLOSED,
            )
        )).scalar() or 0

        # By source
        source_result = await db.execute(
            select(Issue.source, sqla_func.count())
            .group_by(Issue.source)
        )
        by_source = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in source_result.all()
        }

        # By severity
        sev_result = await db.execute(
            select(Issue.severity, sqla_func.count())
            .group_by(Issue.severity)
        )
        by_severity = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in sev_result.all()
        }

        # By status
        status_result = await db.execute(
            select(Issue.status, sqla_func.count())
            .group_by(Issue.status)
        )
        by_status = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in status_result.all()
        }

        return {
            "total": total,
            "open": open_count,
            "overdue": overdue_count,
            "critical_open": critical_count,
            "by_source": by_source,
            "by_severity": by_severity,
            "by_status": by_status,
        }


def _issue_to_dict(issue: Issue) -> dict:
    """Serialize an Issue to dict."""
    return {
        "id": issue.id,
        "title": issue.title,
        "title_ar": issue.title_ar,
        "description": issue.description,
        "description_ar": issue.description_ar,
        "source": issue.source.value,
        "severity": issue.severity.value,
        "status": issue.status.value,
        "escalation_status": issue.escalation_status.value,
        "risk_id": issue.risk_id,
        "control_id": issue.control_id,
        "obligation_id": issue.obligation_id,
        "regulator_id": issue.regulator_id,
        "owner": issue.owner,
        "owner_ar": issue.owner_ar,
        "due_date": issue.due_date.isoformat() if issue.due_date else None,
        "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
        "closure_evidence": issue.closure_evidence,
        "closure_validated_by": issue.closure_validated_by,
        "closure_validated_at": issue.closure_validated_at.isoformat() if issue.closure_validated_at else None,
        "aging_days": _compute_aging_days(issue),
        "tags": issue.tags,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
    }
