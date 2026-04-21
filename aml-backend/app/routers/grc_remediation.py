"""Remediation & Action Tracking API endpoints."""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.remediation_service import RemediationService

router = APIRouter(prefix="/api/grc/remediation", tags=["GRC - Remediation"])


@router.post("")
async def create_action(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new remediation action."""
    result = await RemediationService.create_action(db, data)
    await db.commit()
    return result


@router.get("")
async def list_actions(
    issue_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List remediation actions with filtering."""
    return await RemediationService.list_actions(
        db, issue_id=issue_id, status=status, owner=owner,
        limit=limit, offset=offset,
    )


@router.get("/summary")
async def get_remediation_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get remediation tracking summary statistics."""
    return await RemediationService.get_remediation_summary(db)


@router.get("/{action_id}")
async def get_action(action_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single remediation action."""
    result = await RemediationService.get_action(db, action_id)
    if not result:
        return {"error": "Action not found"}
    return result


@router.put("/{action_id}")
async def update_action(action_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update a remediation action."""
    result = await RemediationService.update_action(db, action_id, data)
    await db.commit()
    return result


@router.delete("/{action_id}")
async def delete_action(action_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a remediation action."""
    result = await RemediationService.delete_action(db, action_id)
    await db.commit()
    return result


# ── Milestones ──

@router.post("/{action_id}/milestones")
async def create_milestone(action_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a milestone within a remediation action."""
    result = await RemediationService.create_milestone(db, action_id, data)
    await db.commit()
    return result


@router.get("/{action_id}/milestones")
async def list_milestones(action_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List milestones for a remediation action."""
    return await RemediationService.list_milestones(db, action_id)


@router.put("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update a milestone."""
    result = await RemediationService.update_milestone(db, milestone_id, data)
    await db.commit()
    return result


@router.delete("/milestones/{milestone_id}")
async def delete_milestone(milestone_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a milestone."""
    result = await RemediationService.delete_milestone(db, milestone_id)
    await db.commit()
    return result
