"""Management Response service — CRUD."""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.audit import ManagementResponse, AuditFinding, ResponseStatus

logger = logging.getLogger(__name__)


class ManagementResponseService:
    """Management response CRUD."""

    @staticmethod
    async def create_response(db: AsyncSession, finding_id: str, data: dict) -> dict:
        result = await db.execute(
            select(AuditFinding).where(AuditFinding.id == finding_id)
        )
        if not result.scalars().first():
            return {"error": "Audit finding not found"}

        resp = ManagementResponse(
            id=generate_uuid(),
            finding_id=finding_id,
            response_text=data["response_text"],
            response_text_ar=data.get("response_text_ar"),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            due_date=_parse_dt(data.get("due_date")),
            status=ResponseStatus(data.get("status", "pending")),
            remediation_action_id=data.get("remediation_action_id"),
            notes=data.get("notes"),
            notes_ar=data.get("notes_ar"),
        )
        db.add(resp)
        await db.flush()
        return _response_to_dict(resp)

    @staticmethod
    async def update_response(db: AsyncSession, response_id: str, data: dict) -> dict:
        result = await db.execute(
            select(ManagementResponse).where(ManagementResponse.id == response_id)
        )
        resp = result.scalars().first()
        if not resp:
            return {"error": "Management response not found"}

        for field in [
            "response_text", "response_text_ar",
            "owner", "owner_ar",
            "remediation_action_id",
            "notes", "notes_ar",
        ]:
            if field in data:
                setattr(resp, field, data[field])

        if "status" in data:
            resp.status = ResponseStatus(data["status"])
            if data["status"] == "completed" and not resp.completed_at:
                resp.completed_at = datetime.utcnow()
        if "due_date" in data:
            resp.due_date = _parse_dt(data["due_date"])

        await db.flush()
        return _response_to_dict(resp)

    @staticmethod
    async def get_response(db: AsyncSession, response_id: str) -> Optional[dict]:
        result = await db.execute(
            select(ManagementResponse).where(ManagementResponse.id == response_id)
        )
        resp = result.scalars().first()
        if not resp:
            return None
        return _response_to_dict(resp)

    @staticmethod
    async def list_responses(
        db: AsyncSession,
        finding_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        stmt = select(ManagementResponse)
        if finding_id:
            stmt = stmt.where(ManagementResponse.finding_id == finding_id)
        if status:
            stmt = stmt.where(ManagementResponse.status == ResponseStatus(status))

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(ManagementResponse.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        responses = result.scalars().all()

        return {
            "items": [_response_to_dict(r) for r in responses],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_response(db: AsyncSession, response_id: str) -> dict:
        result = await db.execute(
            select(ManagementResponse).where(ManagementResponse.id == response_id)
        )
        resp = result.scalars().first()
        if not resp:
            return {"error": "Management response not found"}
        await db.delete(resp)
        await db.flush()
        return {"deleted": response_id}


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _response_to_dict(resp: ManagementResponse) -> dict:
    return {
        "id": resp.id,
        "finding_id": resp.finding_id,
        "response_text": resp.response_text,
        "response_text_ar": resp.response_text_ar,
        "owner": resp.owner,
        "owner_ar": resp.owner_ar,
        "due_date": resp.due_date.isoformat() if resp.due_date else None,
        "completed_at": resp.completed_at.isoformat() if resp.completed_at else None,
        "status": resp.status.value,
        "remediation_action_id": resp.remediation_action_id,
        "notes": resp.notes,
        "notes_ar": resp.notes_ar,
        "created_at": resp.created_at.isoformat() if resp.created_at else None,
        "updated_at": resp.updated_at.isoformat() if resp.updated_at else None,
    }
