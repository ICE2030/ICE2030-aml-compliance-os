"""Audit Engagement API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.audit_engagement_service import AuditEngagementService

router = APIRouter(prefix="/api/grc/audit-engagements", tags=["GRC - Audit Engagements"])


@router.post("")
async def create_engagement(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new audit engagement."""
    result = await AuditEngagementService.create_engagement(db, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.get("")
async def list_engagements(
    plan_id: str = Query(None),
    status: str = Query(None),
    owner: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List audit engagements with optional filters."""
    return await AuditEngagementService.list_engagements(
        db, plan_id=plan_id, status=status, owner=owner, limit=limit, offset=offset
    )


@router.get("/summary")
async def get_engagement_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get audit engagement summary stats."""
    return await AuditEngagementService.get_engagement_summary(db)


@router.get("/{engagement_id}")
async def get_engagement(engagement_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single audit engagement."""
    result = await AuditEngagementService.get_engagement(db, engagement_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit engagement not found")
    return result


@router.put("/{engagement_id}")
async def update_engagement(engagement_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update an audit engagement."""
    result = await AuditEngagementService.update_engagement(db, engagement_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.delete("/{engagement_id}")
async def delete_engagement(engagement_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete an audit engagement."""
    result = await AuditEngagementService.delete_engagement(db, engagement_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result
