"""Management Response API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user, require_roles
from app.models.user import User, UserRole
from app.services.grc.management_response_service import ManagementResponseService
from app.services.grc.grc_audit_service import GRCAuditService

router = APIRouter(prefix="/api/grc/management-responses", tags=["GRC - Management Responses"])


@router.post("/{finding_id}")
async def create_response(finding_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER))):
    """Create a management response to a finding."""
    result = await ManagementResponseService.create_response(db, finding_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await GRCAuditService.log_change(db, "create", "management_response", result["id"], user_id=current_user.id, new_values=data, summary=f"Created response for finding: {finding_id}")
    await db.commit()
    return result


@router.get("")
async def list_responses(
    finding_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List management responses with optional filters."""
    return await ManagementResponseService.list_responses(
        db, finding_id=finding_id, status=status, limit=limit, offset=offset,
    )


@router.get("/{response_id}")
async def get_response(response_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single management response."""
    result = await ManagementResponseService.get_response(db, response_id)
    if not result:
        raise HTTPException(status_code=404, detail="Management response not found")
    return result


@router.put("/{response_id}")
async def update_response(response_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER))):
    """Update a management response."""
    prev = await ManagementResponseService.get_response(db, response_id)
    result = await ManagementResponseService.update_response(db, response_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await GRCAuditService.log_change(db, "update", "management_response", response_id, user_id=current_user.id, prev_values=prev, new_values=data, summary=f"Updated response: {response_id}")
    await db.commit()
    return result


@router.delete("/{response_id}")
async def delete_response(response_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR))):
    """Delete a management response."""
    prev = await ManagementResponseService.get_response(db, response_id)
    result = await ManagementResponseService.delete_response(db, response_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await GRCAuditService.log_change(db, "delete", "management_response", response_id, user_id=current_user.id, prev_values=prev, summary=f"Deleted response: {response_id}")
    await db.commit()
    return result
