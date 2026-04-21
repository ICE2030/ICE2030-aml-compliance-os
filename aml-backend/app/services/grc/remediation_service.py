"""Remediation & Action Tracking service.

Handles:
- RemediationAction CRUD with progress tracking
- ActionMilestone management
- Progress aggregation
- Closure validation
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.issue import (
    RemediationAction, ActionMilestone, RemediationStatus, Issue,
)

logger = logging.getLogger(__name__)


class RemediationService:
    """Remediation action and milestone management."""

    @staticmethod
    async def create_action(db: AsyncSession, data: dict) -> dict:
        """Create a remediation action for an issue."""
        # Verify issue exists
        issue = (await db.execute(
            select(Issue).where(Issue.id == data["issue_id"])
        )).scalars().first()
        if not issue:
            return {"error": "Issue not found"}

        action = RemediationAction(
            id=generate_uuid(),
            issue_id=data["issue_id"],
            title=data["title"],
            title_ar=data.get("title_ar"),
            description=data["description"],
            description_ar=data.get("description_ar"),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            status=RemediationStatus(data.get("status", "not_started")),
            progress_pct=data.get("progress_pct", 0),
            blockers=data.get("blockers"),
            closure_test=data.get("closure_test"),
            effectiveness_check=data.get("effectiveness_check"),
        )
        if data.get("target_date"):
            action.target_date = datetime.fromisoformat(data["target_date"])

        db.add(action)
        await db.flush()
        return _action_to_dict(action)

    @staticmethod
    async def update_action(db: AsyncSession, action_id: str, data: dict) -> dict:
        """Update a remediation action."""
        result = await db.execute(
            select(RemediationAction).where(RemediationAction.id == action_id)
        )
        action = result.scalars().first()
        if not action:
            return {"error": "Action not found"}

        for field in [
            "title", "title_ar", "description", "description_ar",
            "owner", "owner_ar", "blockers",
            "closure_test", "effectiveness_check",
        ]:
            if field in data:
                setattr(action, field, data[field])

        if "status" in data:
            new_status = RemediationStatus(data["status"])
            if new_status == RemediationStatus.COMPLETED and action.status != RemediationStatus.COMPLETED:
                action.completed_at = datetime.now(timezone.utc)
            action.status = new_status
        if "progress_pct" in data:
            action.progress_pct = max(0, min(100, data["progress_pct"]))
        if "target_date" in data and data["target_date"]:
            action.target_date = datetime.fromisoformat(data["target_date"])

        await db.flush()
        return _action_to_dict(action)

    @staticmethod
    async def get_action(db: AsyncSession, action_id: str) -> Optional[dict]:
        """Get a single remediation action by ID."""
        result = await db.execute(
            select(RemediationAction).where(RemediationAction.id == action_id)
        )
        action = result.scalars().first()
        if not action:
            return None
        return _action_to_dict(action)

    @staticmethod
    async def list_actions(
        db: AsyncSession,
        issue_id: Optional[str] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List remediation actions with filtering."""
        stmt = select(RemediationAction)

        if issue_id:
            stmt = stmt.where(RemediationAction.issue_id == issue_id)
        if status:
            stmt = stmt.where(RemediationAction.status == RemediationStatus(status))
        if owner:
            stmt = stmt.where(RemediationAction.owner == owner)

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(RemediationAction.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        actions = result.scalars().all()

        return {
            "items": [_action_to_dict(a) for a in actions],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_action(db: AsyncSession, action_id: str) -> dict:
        """Delete a remediation action."""
        result = await db.execute(
            select(RemediationAction).where(RemediationAction.id == action_id)
        )
        action = result.scalars().first()
        if not action:
            return {"error": "Action not found"}
        await db.delete(action)
        await db.flush()
        return {"deleted": action_id}

    # ── Milestones ──

    @staticmethod
    async def create_milestone(db: AsyncSession, action_id: str, data: dict) -> dict:
        """Create a milestone within a remediation action."""
        action = (await db.execute(
            select(RemediationAction).where(RemediationAction.id == action_id)
        )).scalars().first()
        if not action:
            return {"error": "Action not found"}

        milestone = ActionMilestone(
            id=generate_uuid(),
            action_id=action_id,
            title=data["title"],
            title_ar=data.get("title_ar"),
            is_completed=data.get("is_completed", False),
            notes=data.get("notes"),
        )
        if data.get("target_date"):
            milestone.target_date = datetime.fromisoformat(data["target_date"])

        db.add(milestone)
        await db.flush()
        return _milestone_to_dict(milestone)

    @staticmethod
    async def update_milestone(db: AsyncSession, milestone_id: str, data: dict) -> dict:
        """Update a milestone."""
        result = await db.execute(
            select(ActionMilestone).where(ActionMilestone.id == milestone_id)
        )
        milestone = result.scalars().first()
        if not milestone:
            return {"error": "Milestone not found"}

        for field in ["title", "title_ar", "notes"]:
            if field in data:
                setattr(milestone, field, data[field])

        if "is_completed" in data:
            milestone.is_completed = data["is_completed"]
            if data["is_completed"] and not milestone.completed_at:
                milestone.completed_at = datetime.now(timezone.utc)
        if "target_date" in data and data["target_date"]:
            milestone.target_date = datetime.fromisoformat(data["target_date"])

        await db.flush()
        return _milestone_to_dict(milestone)

    @staticmethod
    async def list_milestones(db: AsyncSession, action_id: str) -> list:
        """List milestones for an action."""
        result = await db.execute(
            select(ActionMilestone)
            .where(ActionMilestone.action_id == action_id)
            .order_by(ActionMilestone.target_date.asc().nulls_last())
        )
        return [_milestone_to_dict(m) for m in result.scalars().all()]

    @staticmethod
    async def delete_milestone(db: AsyncSession, milestone_id: str) -> dict:
        """Delete a milestone."""
        result = await db.execute(
            select(ActionMilestone).where(ActionMilestone.id == milestone_id)
        )
        milestone = result.scalars().first()
        if not milestone:
            return {"error": "Milestone not found"}
        await db.delete(milestone)
        await db.flush()
        return {"deleted": milestone_id}

    @staticmethod
    async def get_remediation_summary(db: AsyncSession) -> dict:
        """Get summary stats for remediation tracking."""
        total = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction)
        )).scalar() or 0

        in_progress = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction).where(
                RemediationAction.status == RemediationStatus.IN_PROGRESS
            )
        )).scalar() or 0

        completed = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction).where(
                RemediationAction.status.in_([RemediationStatus.COMPLETED, RemediationStatus.VERIFIED])
            )
        )).scalar() or 0

        blocked = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction).where(
                RemediationAction.status == RemediationStatus.BLOCKED
            )
        )).scalar() or 0

        overdue = (await db.execute(
            select(sqla_func.count()).select_from(RemediationAction).where(
                RemediationAction.status.in_([RemediationStatus.NOT_STARTED, RemediationStatus.IN_PROGRESS]),
                RemediationAction.target_date < datetime.now(timezone.utc),
            )
        )).scalar() or 0

        avg_progress = (await db.execute(
            select(sqla_func.avg(RemediationAction.progress_pct))
        )).scalar() or 0

        # By status
        status_result = await db.execute(
            select(RemediationAction.status, sqla_func.count())
            .group_by(RemediationAction.status)
        )
        by_status = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in status_result.all()
        }

        return {
            "total": total,
            "in_progress": in_progress,
            "completed": completed,
            "blocked": blocked,
            "overdue": overdue,
            "avg_progress_pct": round(float(avg_progress), 1),
            "by_status": by_status,
        }


def _action_to_dict(action: RemediationAction) -> dict:
    """Serialize a RemediationAction to dict."""
    return {
        "id": action.id,
        "issue_id": action.issue_id,
        "title": action.title,
        "title_ar": action.title_ar,
        "description": action.description,
        "description_ar": action.description_ar,
        "owner": action.owner,
        "owner_ar": action.owner_ar,
        "target_date": action.target_date.isoformat() if action.target_date else None,
        "completed_at": action.completed_at.isoformat() if action.completed_at else None,
        "status": action.status.value,
        "progress_pct": action.progress_pct,
        "blockers": action.blockers,
        "closure_test": action.closure_test,
        "effectiveness_check": action.effectiveness_check,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
    }


def _milestone_to_dict(milestone: ActionMilestone) -> dict:
    """Serialize an ActionMilestone to dict."""
    return {
        "id": milestone.id,
        "action_id": milestone.action_id,
        "title": milestone.title,
        "title_ar": milestone.title_ar,
        "target_date": milestone.target_date.isoformat() if milestone.target_date else None,
        "completed_at": milestone.completed_at.isoformat() if milestone.completed_at else None,
        "is_completed": milestone.is_completed,
        "notes": milestone.notes,
        "created_at": milestone.created_at.isoformat() if milestone.created_at else None,
    }
