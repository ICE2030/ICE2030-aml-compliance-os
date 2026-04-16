import hashlib
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.audit import AuditLog
from app.models.base import generate_uuid


class AuditService:
    @staticmethod
    async def log(
        db: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
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
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        db.add(audit_log)
        await db.flush()
        return audit_log

    @staticmethod
    async def verify_chain(db: AsyncSession) -> dict:
        """Verify the integrity of the audit log chain."""
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.created_at)
        )
        logs = result.scalars().all()
        if not logs:
            return {"valid": True, "total": 0}

        broken_at = None
        for i, log in enumerate(logs):
            if i == 0:
                if log.previous_hash != "GENESIS":
                    broken_at = log.id
                    break
            else:
                if log.previous_hash != logs[i - 1].entry_hash:
                    broken_at = log.id
                    break

        return {
            "valid": broken_at is None,
            "total": len(logs),
            "broken_at": broken_at,
        }
