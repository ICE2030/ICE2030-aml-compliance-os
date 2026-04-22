"""P2 — GRC Entity Audit Logging service.

Extends the existing AuditService to track prev/new values for all GRC entities.
Provides an immutable audit trail with:
- Previous values (before change)
- New values (after change)
- Action type (create/update/delete)
- Timestamp and user tracking
- Hash chain for immutability
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, desc, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.models.base import generate_uuid

logger = logging.getLogger(__name__)


class GRCAuditService:
    """Extended audit logging for GRC entities with prev/new value tracking."""

    @staticmethod
    async def log_change(
        db: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: Optional[str] = None,
        prev_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        summary: Optional[str] = None,
        summary_ar: Optional[str] = None,
    ) -> dict:
        """Log a GRC entity change with prev/new values.

        Args:
            action: 'create', 'update', or 'delete'
            resource_type: Entity type (e.g., 'enterprise_risk', 'issue', 'grc_action')
            resource_id: Entity ID
            user_id: User performing the change
            prev_values: Previous field values (for update/delete)
            new_values: New field values (for create/update)
            summary: Human-readable change summary
            summary_ar: Arabic change summary
        """
        # Compute changed fields for update actions
        changed_fields = []
        if action == "update" and prev_values and new_values:
            for key in new_values:
                if key in prev_values and prev_values[key] != new_values[key]:
                    changed_fields.append(key)

        details = {
            "prev_values": prev_values,
            "new_values": new_values,
            "changed_fields": changed_fields,
            "summary": summary,
            "summary_ar": summary_ar,
        }

        # Get previous hash for chain
        result = await db.execute(
            select(AuditLog).order_by(desc(AuditLog.created_at)).limit(1)
        )
        last_log = result.scalar_one_or_none()
        previous_hash = last_log.entry_hash if last_log else "GENESIS"

        # Create hash for immutability
        hash_data = json.dumps({
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_id,
            "details": details,
            "previous_hash": previous_hash,
        }, sort_keys=True, default=str)
        entry_hash = hashlib.sha256(hash_data.encode()).hexdigest()

        audit_log = AuditLog(
            id=generate_uuid(),
            action=f"grc_{action}",
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            details=details,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        db.add(audit_log)
        await db.flush()

        return {
            "id": audit_log.id,
            "action": audit_log.action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "changed_fields": changed_fields,
        }

    @staticmethod
    async def get_entity_history(
        db: AsyncSession,
        resource_type: str,
        resource_id: str,
        limit: int = 50,
    ) -> list:
        """Get audit history for a specific GRC entity."""
        result = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        logs = result.scalars().all()
        return [
            {
                "id": log.id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "user_id": log.user_id,
                "details": log.details,
                "entry_hash": log.entry_hash,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    @staticmethod
    async def get_recent_changes(
        db: AsyncSession,
        resource_type: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """Get recent GRC audit trail entries."""
        stmt = select(AuditLog).where(
            AuditLog.action.like("grc_%")
        )
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit)
        result = await db.execute(stmt)
        logs = result.scalars().all()

        return {
            "items": [
                {
                    "id": log.id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "user_id": log.user_id,
                    "details": log.details,
                    "entry_hash": log.entry_hash,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
            "total": total,
        }
