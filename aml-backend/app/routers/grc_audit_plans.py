"""Audit Plan API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.audit_plan_service import AuditPlanService

router = APIRouter(prefix="/api/grc/audit-plans", tags=["GRC - Audit Plans"])


@router.post("")
async def create_plan(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new audit plan."""
    result = await AuditPlanService.create_plan(db, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await db.commit()
    return result


@router.get("")
async def list_plans(
    status: str = Query(None),
    owner: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List audit plans with optional filters."""
    return await AuditPlanService.list_plans(db, status=status, owner=owner, limit=limit, offset=offset)


@router.get("/summary")
async def get_plan_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get audit plan summary stats."""
    return await AuditPlanService.get_plan_summary(db)


@router.get("/{plan_id}")
async def get_plan(plan_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single audit plan."""
    result = await AuditPlanService.get_plan(db, plan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit plan not found")
    return result


@router.put("/{plan_id}")
async def update_plan(plan_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update an audit plan."""
    result = await AuditPlanService.update_plan(db, plan_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete an audit plan."""
    result = await AuditPlanService.delete_plan(db, plan_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result
