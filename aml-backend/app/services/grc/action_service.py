"""GRC Action service — CRUD, filters, overdue detection, summary, and alert/pattern conversion."""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, case, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.action import (
    GRCAction, ActionPriority, ActionStatus, ActionSourceType, ActionOrigin,
)

logger = logging.getLogger(__name__)


class ActionService:
    """Unified action CRUD, filtering, and aggregation."""

    @staticmethod
    async def create_action(db: AsyncSession, data: dict) -> dict:
        action = GRCAction(
            id=generate_uuid(),
            title=data["title"],
            title_ar=data.get("title_ar"),
            description=data.get("description"),
            description_ar=data.get("description_ar"),
            reason=data.get("reason"),
            reason_ar=data.get("reason_ar"),
            source_type=ActionSourceType(data.get("source_type", "manual")),
            source_id=data.get("source_id"),
            source_title=data.get("source_title"),
            origin=ActionOrigin(data.get("origin", "manual")),
            priority=ActionPriority(data.get("priority", "medium")),
            status=ActionStatus(data.get("status", "open")),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            due_date=_parse_dt(data.get("due_date")),
            linked_risk_ids=data.get("linked_risk_ids"),
            linked_issue_ids=data.get("linked_issue_ids"),
            linked_finding_ids=data.get("linked_finding_ids"),
            linked_obligation_ids=data.get("linked_obligation_ids"),
            linked_control_ids=data.get("linked_control_ids"),
            linked_evidence_ids=data.get("linked_evidence_ids"),
            tags=data.get("tags"),
        )
        db.add(action)
        await db.flush()
        return _action_to_dict(action)

    @staticmethod
    async def update_action(db: AsyncSession, action_id: str, data: dict) -> dict:
        result = await db.execute(select(GRCAction).where(GRCAction.id == action_id))
        action = result.scalars().first()
        if not action:
            return {"error": "Action not found"}

        for field in [
            "title", "title_ar", "description", "description_ar",
            "reason", "reason_ar", "source_title",
            "owner", "owner_ar",
            "resolution_notes", "resolution_notes_ar",
            "linked_risk_ids", "linked_issue_ids", "linked_finding_ids",
            "linked_obligation_ids", "linked_control_ids", "linked_evidence_ids",
            "tags",
        ]:
            if field in data:
                setattr(action, field, data[field])

        if "source_type" in data:
            action.source_type = ActionSourceType(data["source_type"])
        if "source_id" in data:
            action.source_id = data["source_id"]
        if "origin" in data:
            action.origin = ActionOrigin(data["origin"])
        if "priority" in data:
            action.priority = ActionPriority(data["priority"])
        if "status" in data:
            new_status = ActionStatus(data["status"])
            action.status = new_status
            if new_status == ActionStatus.COMPLETED and not action.completed_at:
                action.completed_at = datetime.now(timezone.utc)
        if "due_date" in data:
            action.due_date = _parse_dt(data["due_date"])

        await db.flush()
        return _action_to_dict(action)

    @staticmethod
    async def get_action(db: AsyncSession, action_id: str) -> Optional[dict]:
        result = await db.execute(select(GRCAction).where(GRCAction.id == action_id))
        action = result.scalars().first()
        if not action:
            return None
        return _action_to_dict(action)

    @staticmethod
    async def list_actions(
        db: AsyncSession,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        source_type: Optional[str] = None,
        owner: Optional[str] = None,
        origin: Optional[str] = None,
        overdue_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        stmt = select(GRCAction)

        if status:
            stmt = stmt.where(GRCAction.status == ActionStatus(status))
        if priority:
            stmt = stmt.where(GRCAction.priority == ActionPriority(priority))
        if source_type:
            stmt = stmt.where(GRCAction.source_type == ActionSourceType(source_type))
        if owner:
            stmt = stmt.where(GRCAction.owner == owner)
        if origin:
            stmt = stmt.where(GRCAction.origin == ActionOrigin(origin))
        if overdue_only:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                GRCAction.due_date < now,
            )

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        # Order by priority (critical first), then due date
        stmt = stmt.order_by(GRCAction.created_at.desc()).offset(offset).limit(limit)
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
        result = await db.execute(select(GRCAction).where(GRCAction.id == action_id))
        action = result.scalars().first()
        if not action:
            return {"error": "Action not found"}
        await db.delete(action)
        await db.flush()
        return {"deleted": action_id}

    @staticmethod
    async def get_action_summary(db: AsyncSession) -> dict:
        total = (await db.execute(
            select(sqla_func.count()).select_from(GRCAction)
        )).scalar() or 0

        open_count = (await db.execute(
            select(sqla_func.count()).select_from(GRCAction).where(
                GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS])
            )
        )).scalar() or 0

        overdue_count = (await db.execute(
            select(sqla_func.count()).select_from(GRCAction).where(
                GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                GRCAction.due_date < datetime.now(timezone.utc),
            )
        )).scalar() or 0

        completed_count = (await db.execute(
            select(sqla_func.count()).select_from(GRCAction).where(
                GRCAction.status == ActionStatus.COMPLETED
            )
        )).scalar() or 0

        # By priority
        prio_result = await db.execute(
            select(GRCAction.priority, sqla_func.count())
            .where(GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]))
            .group_by(GRCAction.priority)
        )
        by_priority = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in prio_result.all()
        }

        # By source type
        src_result = await db.execute(
            select(GRCAction.source_type, sqla_func.count())
            .group_by(GRCAction.source_type)
        )
        by_source = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in src_result.all()
        }

        # By status
        status_result = await db.execute(
            select(GRCAction.status, sqla_func.count())
            .group_by(GRCAction.status)
        )
        by_status = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in status_result.all()
        }

        # By origin
        origin_result = await db.execute(
            select(GRCAction.origin, sqla_func.count())
            .group_by(GRCAction.origin)
        )
        by_origin = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in origin_result.all()
        }

        return {
            "total": total,
            "open": open_count,
            "overdue": overdue_count,
            "completed": completed_count,
            "by_priority": by_priority,
            "by_source": by_source,
            "by_status": by_status,
            "by_origin": by_origin,
        }

    @staticmethod
    async def get_top_actions(db: AsyncSession, limit: int = 3) -> list:
        """Get top N actions requiring immediate attention (for dashboard)."""
        now = datetime.now(timezone.utc)

        # Priority order: overdue critical > overdue high > open critical > open high
        priority_order = case(
            (GRCAction.priority == ActionPriority.CRITICAL, 1),
            (GRCAction.priority == ActionPriority.HIGH, 2),
            (GRCAction.priority == ActionPriority.MEDIUM, 3),
            (GRCAction.priority == ActionPriority.LOW, 4),
            else_=5,
        )
        stmt = (
            select(GRCAction)
            .where(GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]))
            .order_by(
                priority_order,
                GRCAction.due_date.asc().nulls_last(),
                GRCAction.created_at.asc(),
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        actions = result.scalars().all()
        return [_action_to_dict(a) for a in actions]


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _action_to_dict(action: GRCAction) -> dict:
    return {
        "id": action.id,
        "title": action.title,
        "title_ar": action.title_ar,
        "description": action.description,
        "description_ar": action.description_ar,
        "reason": action.reason,
        "reason_ar": action.reason_ar,
        "source_type": action.source_type.value,
        "source_id": action.source_id,
        "source_title": action.source_title,
        "origin": action.origin.value,
        "priority": action.priority.value,
        "status": action.status.value,
        "owner": action.owner,
        "owner_ar": action.owner_ar,
        "due_date": action.due_date.isoformat() if action.due_date else None,
        "completed_at": action.completed_at.isoformat() if action.completed_at else None,
        "linked_risk_ids": action.linked_risk_ids,
        "linked_issue_ids": action.linked_issue_ids,
        "linked_finding_ids": action.linked_finding_ids,
        "linked_obligation_ids": action.linked_obligation_ids,
        "linked_control_ids": action.linked_control_ids,
        "linked_evidence_ids": action.linked_evidence_ids,
        "resolution_notes": action.resolution_notes,
        "resolution_notes_ar": action.resolution_notes_ar,
        "tags": action.tags,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
    }
