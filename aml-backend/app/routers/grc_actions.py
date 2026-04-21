"""GRC Action Center API endpoints — Phase G3."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user, require_roles
from app.models.user import User, UserRole
from app.services.grc.action_service import ActionService
from app.services.grc.alert_action_service import AlertActionService
from app.services.grc.pattern_action_service import PatternActionService
from app.services.grc.grc_audit_service import GRCAuditService

router = APIRouter(prefix="/api/grc/actions", tags=["GRC - Action Center"])


@router.post("")
async def create_action(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST))):
    """Create a new action."""
    result = await ActionService.create_action(db, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await GRCAuditService.log_change(db, "create", "grc_action", result["id"], user_id=current_user.id, new_values=data, summary=f"Created action: {data.get('title', '')}")
    await db.commit()
    return result


@router.get("")
async def list_actions(
    status: str = Query(None),
    priority: str = Query(None),
    source_type: str = Query(None),
    owner: str = Query(None),
    origin: str = Query(None),
    overdue_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List actions with optional filters."""
    return await ActionService.list_actions(
        db, status=status, priority=priority, source_type=source_type,
        owner=owner, origin=origin, overdue_only=overdue_only,
        limit=limit, offset=offset,
    )


@router.get("/summary")
async def get_action_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get action summary stats."""
    return await ActionService.get_action_summary(db)


@router.get("/top")
async def get_top_actions(
    limit: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get top N actions requiring immediate attention."""
    return await ActionService.get_top_actions(db, limit=limit)


@router.post("/scan-alerts")
async def scan_alerts(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Scan for alert conditions and generate actions."""
    result = await AlertActionService.scan_and_generate(db)
    await db.commit()
    return result


@router.post("/scan-patterns")
async def scan_patterns(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Scan detected patterns and generate suggested actions."""
    result = await PatternActionService.generate_from_patterns(db)
    await db.commit()
    return result


@router.post("/{action_id}/approve")
async def approve_pattern_action(action_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Approve a pattern-generated action."""
    result = await PatternActionService.approve_pattern_action(db, action_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await db.commit()
    return result


@router.get("/{action_id}")
async def get_action(action_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single action."""
    result = await ActionService.get_action(db, action_id)
    if not result:
        raise HTTPException(status_code=404, detail="Action not found")
    return result


@router.put("/{action_id}")
async def update_action(action_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.ANALYST))):
    """Update an action."""
    prev = await ActionService.get_action(db, action_id)
    result = await ActionService.update_action(db, action_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await GRCAuditService.log_change(db, "update", "grc_action", action_id, user_id=current_user.id, prev_values=prev, new_values=data, summary=f"Updated action: {action_id}")
    await db.commit()
    return result


@router.delete("/{action_id}")
async def delete_action(action_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER))):
    """Delete an action."""
    prev = await ActionService.get_action(db, action_id)
    result = await ActionService.delete_action(db, action_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await GRCAuditService.log_change(db, "delete", "grc_action", action_id, user_id=current_user.id, prev_values=prev, summary=f"Deleted action: {action_id}")
    await db.commit()
    return result
