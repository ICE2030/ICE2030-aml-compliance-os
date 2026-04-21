"""Audit Finding API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.audit_finding_service import AuditFindingService

router = APIRouter(prefix="/api/grc/audit-findings", tags=["GRC - Audit Findings"])


@router.post("/{engagement_id}")
async def create_finding(engagement_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create an audit finding within an engagement."""
    result = await AuditFindingService.create_finding(db, engagement_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.get("")
async def list_findings(
    engagement_id: str = Query(None),
    severity: str = Query(None),
    status: str = Query(None),
    owner: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List audit findings with optional filters."""
    return await AuditFindingService.list_findings(
        db, engagement_id=engagement_id, severity=severity,
        status=status, owner=owner, limit=limit, offset=offset,
    )


@router.get("/summary")
async def get_finding_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get audit finding summary stats."""
    return await AuditFindingService.get_finding_summary(db)


@router.get("/{finding_id}")
async def get_finding(finding_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single audit finding."""
    result = await AuditFindingService.get_finding(db, finding_id)
    if not result:
        raise HTTPException(status_code=404, detail="Audit finding not found")
    return result


@router.put("/{finding_id}")
async def update_finding(finding_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update an audit finding."""
    result = await AuditFindingService.update_finding(db, finding_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.delete("/{finding_id}")
async def delete_finding(finding_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete an audit finding."""
    result = await AuditFindingService.delete_finding(db, finding_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result
