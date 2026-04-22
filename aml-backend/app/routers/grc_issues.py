"""Issue Management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user, require_roles
from app.models.user import User, UserRole
from app.services.grc.issue_management_service import IssueManagementService
from app.services.grc.grc_audit_service import GRCAuditService

router = APIRouter(prefix="/api/grc/issues", tags=["GRC - Issue Management"])


@router.post("")
async def create_issue(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST))):
    """Create a new issue."""
    result = await IssueManagementService.create_issue(db, data)
    await GRCAuditService.log_change(db, "create", "issue", result["id"], user_id=current_user.id, new_values=data, summary=f"Created issue: {data.get('title', '')}")
    await db.commit()
    return result


@router.get("")
async def list_issues(
    source: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    risk_id: Optional[str] = Query(None),
    obligation_id: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List issues with filtering."""
    return await IssueManagementService.list_issues(
        db, source=source, severity=severity, status=status,
        risk_id=risk_id, obligation_id=obligation_id, owner=owner,
        limit=limit, offset=offset,
    )


@router.get("/summary")
async def get_issue_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get issue management summary statistics."""
    return await IssueManagementService.get_issue_summary(db)


@router.get("/{issue_id}")
async def get_issue(issue_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single issue."""
    result = await IssueManagementService.get_issue(db, issue_id)
    if not result:
        raise HTTPException(status_code=404, detail="Issue not found")
    return result


@router.put("/{issue_id}")
async def update_issue(issue_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST))):
    """Update an issue."""
    prev = await IssueManagementService.get_issue(db, issue_id)
    result = await IssueManagementService.update_issue(db, issue_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await GRCAuditService.log_change(db, "update", "issue", issue_id, user_id=current_user.id, prev_values=prev, new_values=data, summary=f"Updated issue: {issue_id}")
    await db.commit()
    return result


@router.delete("/{issue_id}")
async def delete_issue(issue_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER))):
    """Delete an issue."""
    prev = await IssueManagementService.get_issue(db, issue_id)
    result = await IssueManagementService.delete_issue(db, issue_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await GRCAuditService.log_change(db, "delete", "issue", issue_id, user_id=current_user.id, prev_values=prev, summary=f"Deleted issue: {issue_id}")
    await db.commit()
    return result
