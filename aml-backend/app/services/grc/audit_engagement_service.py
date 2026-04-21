"""Audit Engagement service — CRUD and summary."""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.audit import AuditEngagement, AuditPlan, EngagementStatus

logger = logging.getLogger(__name__)


class AuditEngagementService:
    """Audit engagement CRUD."""

    @staticmethod
    async def create_engagement(db: AsyncSession, data: dict) -> dict:
        # Verify plan exists
        plan_id = data.get("plan_id")
        if plan_id:
            result = await db.execute(select(AuditPlan).where(AuditPlan.id == plan_id))
            if not result.scalars().first():
                return {"error": "Audit plan not found"}

        engagement = AuditEngagement(
            id=generate_uuid(),
            plan_id=plan_id,
            title=data["title"],
            title_ar=data.get("title_ar"),
            description=data.get("description"),
            description_ar=data.get("description_ar"),
            scope=data.get("scope"),
            scope_ar=data.get("scope_ar"),
            objectives=data.get("objectives"),
            objectives_ar=data.get("objectives_ar"),
            start_date=_parse_dt(data.get("start_date")),
            end_date=_parse_dt(data.get("end_date")),
            risk_ids=data.get("risk_ids"),
            control_ids=data.get("control_ids"),
            obligation_ids=data.get("obligation_ids"),
            evidence_ids=data.get("evidence_ids"),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            status=EngagementStatus(data.get("status", "planned")),
            tags=data.get("tags"),
        )
        db.add(engagement)
        await db.flush()
        return _engagement_to_dict(engagement)

    @staticmethod
    async def update_engagement(db: AsyncSession, engagement_id: str, data: dict) -> dict:
        result = await db.execute(
            select(AuditEngagement).where(AuditEngagement.id == engagement_id)
        )
        eng = result.scalars().first()
        if not eng:
            return {"error": "Audit engagement not found"}

        for field in [
            "title", "title_ar", "description", "description_ar",
            "scope", "scope_ar", "objectives", "objectives_ar",
            "risk_ids", "control_ids", "obligation_ids", "evidence_ids",
            "owner", "owner_ar", "tags",
        ]:
            if field in data:
                setattr(eng, field, data[field])

        if "status" in data:
            eng.status = EngagementStatus(data["status"])
        if "start_date" in data:
            eng.start_date = _parse_dt(data["start_date"])
        if "end_date" in data:
            eng.end_date = _parse_dt(data["end_date"])

        await db.flush()
        return _engagement_to_dict(eng)

    @staticmethod
    async def get_engagement(db: AsyncSession, engagement_id: str) -> Optional[dict]:
        result = await db.execute(
            select(AuditEngagement).where(AuditEngagement.id == engagement_id)
        )
        eng = result.scalars().first()
        if not eng:
            return None
        return _engagement_to_dict(eng)

    @staticmethod
    async def list_engagements(
        db: AsyncSession,
        plan_id: Optional[str] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        stmt = select(AuditEngagement)
        if plan_id:
            stmt = stmt.where(AuditEngagement.plan_id == plan_id)
        if status:
            stmt = stmt.where(AuditEngagement.status == EngagementStatus(status))
        if owner:
            stmt = stmt.where(AuditEngagement.owner == owner)

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(AuditEngagement.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        engs = result.scalars().all()

        return {
            "items": [_engagement_to_dict(e) for e in engs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_engagement(db: AsyncSession, engagement_id: str) -> dict:
        result = await db.execute(
            select(AuditEngagement).where(AuditEngagement.id == engagement_id)
        )
        eng = result.scalars().first()
        if not eng:
            return {"error": "Audit engagement not found"}
        await db.delete(eng)
        await db.flush()
        return {"deleted": engagement_id}

    @staticmethod
    async def get_engagement_summary(db: AsyncSession) -> dict:
        total = (await db.execute(
            select(sqla_func.count()).select_from(AuditEngagement)
        )).scalar() or 0

        status_result = await db.execute(
            select(AuditEngagement.status, sqla_func.count())
            .group_by(AuditEngagement.status)
        )
        by_status = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in status_result.all()
        }

        return {"total": total, "by_status": by_status}


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _engagement_to_dict(eng: AuditEngagement) -> dict:
    return {
        "id": eng.id,
        "plan_id": eng.plan_id,
        "title": eng.title,
        "title_ar": eng.title_ar,
        "description": eng.description,
        "description_ar": eng.description_ar,
        "scope": eng.scope,
        "scope_ar": eng.scope_ar,
        "objectives": eng.objectives,
        "objectives_ar": eng.objectives_ar,
        "start_date": eng.start_date.isoformat() if eng.start_date else None,
        "end_date": eng.end_date.isoformat() if eng.end_date else None,
        "risk_ids": eng.risk_ids,
        "control_ids": eng.control_ids,
        "obligation_ids": eng.obligation_ids,
        "evidence_ids": eng.evidence_ids,
        "owner": eng.owner,
        "owner_ar": eng.owner_ar,
        "status": eng.status.value,
        "tags": eng.tags,
        "created_at": eng.created_at.isoformat() if eng.created_at else None,
        "updated_at": eng.updated_at.isoformat() if eng.updated_at else None,
    }
