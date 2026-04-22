"""Usage tracking API — Phase V.

Lightweight endpoints for recording user activity and viewing aggregate
usage. Not a heavy analytics system — see services/usage_service.py.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_roles
from app.models.user import User, UserRole
from app.services.usage_service import UsageService, ALLOWED_EVENT_TYPES

router = APIRouter(prefix="/api/usage", tags=["Usage & Telemetry"])


class UsageEventIn(BaseModel):
    event_type: str = Field(..., description="create|update|delete|navigate|demo_flow_view|seed_load|export|login|logout")
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    path: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/events")
async def record_event(
    event: UsageEventIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a single user-triggered usage event.

    Safe to call from the frontend on every route change — cheap, fire-and-forget.
    """
    created = await UsageService.record_event(
        db,
        event_type=event.event_type,
        user_id=current_user.id,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        path=event.path,
        metadata=event.metadata,
    )
    return {
        "id": created.id,
        "event_type": created.event_type,
        "resource_type": created.resource_type,
        "resource_id": created.resource_id,
        "path": created.path,
        "recorded_at": created.created_at.isoformat() if created.created_at else None,
    }


@router.get("/events")
async def list_events(
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR)
    ),
):
    """List recent usage events (RBAC-protected)."""
    return await UsageService.list_events(
        db,
        event_type=event_type,
        user_id=user_id,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )


@router.get("/summary")
async def usage_summary(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR)
    ),
):
    """Aggregate counts for the usage widget."""
    return await UsageService.summary(db, days=days)


@router.get("/event-types")
async def list_event_types(
    current_user: User = Depends(get_current_user),
):
    """Advertise the allowed event_type strings for frontend dropdowns."""
    return {"event_types": sorted(ALLOWED_EVENT_TYPES)}
