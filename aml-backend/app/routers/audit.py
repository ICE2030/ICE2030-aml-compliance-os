import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse, AuditExportRequest
from app.services.audit_service import AuditService
import io
import csv

router = APIRouter(prefix="/api/audit", tags=["Audit & Evidence"])


@router.get("/logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    resource_type: str = Query(None),
    action: str = Query(None),
    user_id: str = Query(None),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not authorized to view audit logs")

    query = select(AuditLog)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    query = query.offset(skip).limit(limit).order_by(AuditLog.created_at.desc())
    result = await db.execute(query)
    return [AuditLogResponse.model_validate(l) for l in result.scalars().all()]


@router.get("/verify-chain")
async def verify_audit_chain(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not authorized")
    result = await AuditService.verify_chain(db)
    return result


@router.post("/export")
async def export_audit_logs(
    request: AuditExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR]:
        raise HTTPException(status_code=403, detail="Not authorized")

    query = select(AuditLog)
    if request.resource_type:
        query = query.where(AuditLog.resource_type == request.resource_type)
    if request.action:
        query = query.where(AuditLog.action == request.action)
    query = query.order_by(AuditLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "User ID", "Action", "Resource Type", "Resource ID", "Details", "Hash"])
    for log in logs:
        writer.writerow([
            log.id,
            str(log.created_at),
            log.user_id or "",
            log.action,
            log.resource_type,
            log.resource_id or "",
            json.dumps(log.details) if log.details else "",
            log.entry_hash or "",
        ])

    await AuditService.log(
        db, "export_audit_logs", "audit", None, current_user.id,
        {"filters": request.model_dump(), "total_exported": len(logs)}
    )

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )
