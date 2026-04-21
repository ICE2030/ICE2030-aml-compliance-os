"""Audit Plan service — CRUD and summary."""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.audit import AuditPlan, AuditPlanStatus

logger = logging.getLogger(__name__)


class AuditPlanService:
    """Audit plan CRUD and aggregation."""

    @staticmethod
    async def create_plan(db: AsyncSession, data: dict) -> dict:
        plan = AuditPlan(
            id=generate_uuid(),
            title=data["title"],
            title_ar=data.get("title_ar"),
            description=data.get("description"),
            description_ar=data.get("description_ar"),
            period_start=_parse_dt(data.get("period_start")),
            period_end=_parse_dt(data.get("period_end")),
            scope_summary=data.get("scope_summary"),
            scope_summary_ar=data.get("scope_summary_ar"),
            risk_categories=data.get("risk_categories"),
            regulator_ids=data.get("regulator_ids"),
            topic_ids=data.get("topic_ids"),
            business_units=data.get("business_units"),
            processes=data.get("processes"),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            status=AuditPlanStatus(data.get("status", "draft")),
        )
        db.add(plan)
        await db.flush()
        return _plan_to_dict(plan)

    @staticmethod
    async def update_plan(db: AsyncSession, plan_id: str, data: dict) -> dict:
        result = await db.execute(select(AuditPlan).where(AuditPlan.id == plan_id))
        plan = result.scalars().first()
        if not plan:
            return {"error": "Audit plan not found"}

        for field in [
            "title", "title_ar", "description", "description_ar",
            "scope_summary", "scope_summary_ar",
            "risk_categories", "regulator_ids", "topic_ids",
            "business_units", "processes",
            "owner", "owner_ar",
        ]:
            if field in data:
                setattr(plan, field, data[field])

        if "status" in data:
            plan.status = AuditPlanStatus(data["status"])
        if "period_start" in data:
            plan.period_start = _parse_dt(data["period_start"])
        if "period_end" in data:
            plan.period_end = _parse_dt(data["period_end"])

        await db.flush()
        return _plan_to_dict(plan)

    @staticmethod
    async def get_plan(db: AsyncSession, plan_id: str) -> Optional[dict]:
        result = await db.execute(select(AuditPlan).where(AuditPlan.id == plan_id))
        plan = result.scalars().first()
        if not plan:
            return None
        return _plan_to_dict(plan)

    @staticmethod
    async def list_plans(
        db: AsyncSession,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        stmt = select(AuditPlan)
        if status:
            stmt = stmt.where(AuditPlan.status == AuditPlanStatus(status))
        if owner:
            stmt = stmt.where(AuditPlan.owner == owner)

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(AuditPlan.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        plans = result.scalars().all()

        return {
            "items": [_plan_to_dict(p) for p in plans],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_plan(db: AsyncSession, plan_id: str) -> dict:
        result = await db.execute(select(AuditPlan).where(AuditPlan.id == plan_id))
        plan = result.scalars().first()
        if not plan:
            return {"error": "Audit plan not found"}
        await db.delete(plan)
        await db.flush()
        return {"deleted": plan_id}

    @staticmethod
    async def get_plan_summary(db: AsyncSession) -> dict:
        total = (await db.execute(
            select(sqla_func.count()).select_from(AuditPlan)
        )).scalar() or 0

        status_result = await db.execute(
            select(AuditPlan.status, sqla_func.count())
            .group_by(AuditPlan.status)
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


def _plan_to_dict(plan: AuditPlan) -> dict:
    return {
        "id": plan.id,
        "title": plan.title,
        "title_ar": plan.title_ar,
        "description": plan.description,
        "description_ar": plan.description_ar,
        "period_start": plan.period_start.isoformat() if plan.period_start else None,
        "period_end": plan.period_end.isoformat() if plan.period_end else None,
        "scope_summary": plan.scope_summary,
        "scope_summary_ar": plan.scope_summary_ar,
        "risk_categories": plan.risk_categories,
        "regulator_ids": plan.regulator_ids,
        "topic_ids": plan.topic_ids,
        "business_units": plan.business_units,
        "processes": plan.processes,
        "owner": plan.owner,
        "owner_ar": plan.owner_ar,
        "status": plan.status.value,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }
