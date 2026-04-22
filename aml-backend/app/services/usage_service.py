"""Usage tracking service — Phase V.

Lightweight recording of user activity (create/update/delete/navigate) plus
simple aggregations for the admin usage dashboard. Intentionally minimal —
this is not a full analytics system.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select, func as sqla_func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import generate_uuid
from app.models.usage_event import UsageEvent

# Cap per-event metadata size to keep storage predictable.
_METADATA_MAX_BYTES = 2048

# Events over this age are returned but paginated; we don't delete them —
# the DB is small and keeping a short tail of history is useful for demos.
ALLOWED_EVENT_TYPES = {
    "create", "update", "delete",
    "navigate", "demo_flow_view", "seed_load", "export",
    "login", "logout",
}


def _trim_metadata(raw: Optional[dict]) -> Optional[dict]:
    """Truncate metadata to keep rows small; drop oversized values."""
    if not raw:
        return None
    trimmed: dict = {}
    for key, value in raw.items():
        if not isinstance(key, str) or len(key) > 80:
            continue
        if isinstance(value, str) and len(value) > 500:
            trimmed[key] = value[:500] + "…"
        elif isinstance(value, (int, float, bool)) or value is None:
            trimmed[key] = value
        elif isinstance(value, (list, dict)):
            serialized = str(value)
            if len(serialized) > 500:
                trimmed[key] = serialized[:500] + "…"
            else:
                trimmed[key] = value
        else:
            trimmed[key] = str(value)[:500]
    serialized_all = str(trimmed)
    if len(serialized_all) > _METADATA_MAX_BYTES:
        return {"_truncated": True, "keys": list(trimmed.keys())[:20]}
    return trimmed


class UsageService:
    """CRUD + aggregation for UsageEvent records."""

    @staticmethod
    async def record_event(
        db: AsyncSession,
        *,
        event_type: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> UsageEvent:
        """Persist a usage event. Unknown event types are remapped to 'other'."""
        if event_type not in ALLOWED_EVENT_TYPES:
            event_type = "other"
        event = UsageEvent(
            id=generate_uuid(),
            user_id=user_id,
            event_type=event_type,
            resource_type=(resource_type or None),
            resource_id=(resource_id or None),
            path=(path or None)[:300] if path else None,
            metadata_json=_trim_metadata(metadata),
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def record_event_safely(
        db: AsyncSession,
        **kwargs,
    ) -> None:
        """Fire-and-forget event recording that never raises.

        Used inside request handlers so a telemetry failure cannot break a
        user-visible action.
        """
        try:
            await UsageService.record_event(db, **kwargs)
        except Exception:
            # Intentionally swallowed — this is a best-effort telemetry call.
            pass

    @staticmethod
    async def list_events(
        db: AsyncSession,
        *,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        stmt = select(UsageEvent).order_by(desc(UsageEvent.created_at))
        if event_type:
            stmt = stmt.where(UsageEvent.event_type == event_type)
        if user_id:
            stmt = stmt.where(UsageEvent.user_id == user_id)
        if resource_type:
            stmt = stmt.where(UsageEvent.resource_type == resource_type)
        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        stmt = stmt.limit(limit).offset(offset)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return {
            "total": int(total or 0),
            "items": [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "event_type": row.event_type,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "path": row.path,
                    "metadata": row.metadata_json or {},
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
        }

    @staticmethod
    async def summary(db: AsyncSession, *, days: int = 7) -> dict:
        """Basic aggregations for the admin usage widget."""
        since = datetime.now(timezone.utc) - timedelta(days=max(1, days))

        total_stmt = select(sqla_func.count(UsageEvent.id)).where(
            UsageEvent.created_at >= since
        )
        total = int((await db.execute(total_stmt)).scalar_one() or 0)

        by_type_stmt = (
            select(UsageEvent.event_type, sqla_func.count(UsageEvent.id))
            .where(UsageEvent.created_at >= since)
            .group_by(UsageEvent.event_type)
        )
        by_type_rows = (await db.execute(by_type_stmt)).all()
        by_type = {row[0]: int(row[1]) for row in by_type_rows}

        by_resource_stmt = (
            select(UsageEvent.resource_type, sqla_func.count(UsageEvent.id))
            .where(
                UsageEvent.created_at >= since,
                UsageEvent.resource_type.is_not(None),
            )
            .group_by(UsageEvent.resource_type)
        )
        by_resource_rows = (await db.execute(by_resource_stmt)).all()
        by_resource = {row[0]: int(row[1]) for row in by_resource_rows}

        top_paths_stmt = (
            select(UsageEvent.path, sqla_func.count(UsageEvent.id))
            .where(
                UsageEvent.created_at >= since,
                UsageEvent.event_type == "navigate",
                UsageEvent.path.is_not(None),
            )
            .group_by(UsageEvent.path)
            .order_by(desc(sqla_func.count(UsageEvent.id)))
            .limit(10)
        )
        top_paths = [
            {"path": row[0], "count": int(row[1])}
            for row in (await db.execute(top_paths_stmt)).all()
        ]

        active_users_stmt = (
            select(sqla_func.count(sqla_func.distinct(UsageEvent.user_id)))
            .where(
                UsageEvent.created_at >= since,
                UsageEvent.user_id.is_not(None),
            )
        )
        active_users = int(
            (await db.execute(active_users_stmt)).scalar_one() or 0
        )

        return {
            "window_days": days,
            "since": since.isoformat(),
            "total_events": total,
            "active_users": active_users,
            "by_event_type": by_type,
            "by_resource_type": by_resource,
            "top_paths": top_paths,
        }
