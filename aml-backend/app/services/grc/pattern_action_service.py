"""Pattern-to-Action bridge service — Phase G3.

For each detected pattern from Phase 5B pattern detection,
generate a suggested action with explanation, linked entities,
recommended owner, and priority.

Actions start as 'pattern_generated' origin and can be approved
(converted to real actions) by a user.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.action import GRCAction, ActionPriority, ActionStatus, ActionSourceType, ActionOrigin

logger = logging.getLogger(__name__)


class PatternActionService:
    """Generate suggested actions from detected patterns."""

    @staticmethod
    async def generate_from_patterns(db: AsyncSession) -> dict:
        """Query the pattern detection results and generate suggested actions."""
        now = datetime.now(timezone.utc)
        generated = []

        # Import pattern models dynamically to avoid circular imports
        try:
            from app.models.compliance_snapshot import CompliancePattern
        except ImportError:
            return {"scanned_at": now.isoformat(), "actions_generated": 0, "details": [], "note": "Pattern model not available"}

        # Get recent unactioned patterns
        try:
            patterns = await db.execute(
                select(CompliancePattern).where(
                    CompliancePattern.is_active == True
                ).order_by(CompliancePattern.created_at.desc()).limit(50)
            )
            for pattern in patterns.scalars().all():
                # Check if action already exists for this pattern
                existing = await db.execute(
                    select(sqla_func.count()).select_from(GRCAction).where(
                        GRCAction.source_type == ActionSourceType.PATTERN,
                        GRCAction.source_id == pattern.id,
                        GRCAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),
                    )
                )
                if (existing.scalar() or 0) > 0:
                    continue

                # Determine priority based on pattern severity/confidence
                severity = (pattern.severity or "medium").lower() if hasattr(pattern, "severity") else "medium"
                confidence = pattern.confidence if hasattr(pattern, "confidence") else 0.5

                if severity == "critical" or confidence >= 0.9:
                    priority = ActionPriority.CRITICAL
                elif severity == "high" or confidence >= 0.7:
                    priority = ActionPriority.HIGH
                elif severity == "medium":
                    priority = ActionPriority.MEDIUM
                else:
                    priority = ActionPriority.LOW

                # Build linked entity IDs from pattern
                linked_control_ids = None
                linked_risk_ids = None
                if hasattr(pattern, "control_ids") and pattern.control_ids:
                    linked_control_ids = pattern.control_ids
                if hasattr(pattern, "risk_ids") and pattern.risk_ids:
                    linked_risk_ids = pattern.risk_ids

                pattern_type = pattern.pattern_type if hasattr(pattern, "pattern_type") else "unknown"
                pattern_desc = pattern.description if hasattr(pattern, "description") else str(pattern.id)

                action = GRCAction(
                    id=generate_uuid(),
                    title=f"Review detected pattern: {pattern_type}",
                    title_ar=f"مراجعة النمط المكتشف: {pattern_type}",
                    description=f"Pattern detected: {pattern_desc}. Confidence: {confidence:.0%}. Review and decide whether to take corrective action.",
                    description_ar=f"تم اكتشاف نمط: {pattern_desc}. الثقة: {confidence:.0%}. راجع وقرر ما إذا كان يجب اتخاذ إجراء تصحيحي.",
                    reason=f"Automated pattern detection flagged a {pattern_type} pattern that may indicate a systemic issue.",
                    reason_ar=f"اكتشاف الأنماط الآلي أشار إلى نمط {pattern_type} قد يشير إلى مشكلة منهجية.",
                    source_type=ActionSourceType.PATTERN,
                    source_id=pattern.id,
                    source_title=f"Pattern: {pattern_type}",
                    origin=ActionOrigin.PATTERN_GENERATED,
                    priority=priority,
                    status=ActionStatus.OPEN,
                    due_date=now + timedelta(days=14),
                    linked_control_ids=linked_control_ids,
                    linked_risk_ids=linked_risk_ids,
                    tags={"pattern_type": pattern_type, "confidence": confidence},
                )
                db.add(action)
                generated.append({
                    "type": "pattern",
                    "pattern_type": pattern_type,
                    "title": action.title,
                    "priority": priority.value,
                    "source_id": pattern.id,
                })
        except Exception as e:
            logger.warning(f"Pattern-to-action scan failed: {e}")

        await db.flush()
        return {
            "scanned_at": now.isoformat(),
            "actions_generated": len(generated),
            "details": generated,
        }

    @staticmethod
    async def approve_pattern_action(db: AsyncSession, action_id: str) -> dict:
        """Approve a pattern-generated action — convert to a real tracked action."""
        result = await db.execute(select(GRCAction).where(GRCAction.id == action_id))
        action = result.scalars().first()
        if not action:
            return {"error": "Action not found"}
        if action.origin != ActionOrigin.PATTERN_GENERATED:
            return {"error": "Action is not pattern-generated"}

        # Mark as in_progress (approved)
        action.status = ActionStatus.IN_PROGRESS
        action.tags = {**(action.tags or {}), "approved": True, "approved_at": datetime.now(timezone.utc).isoformat()}
        await db.flush()

        return {
            "id": action.id,
            "status": "approved",
            "message": "Pattern-generated action approved and converted to tracked action.",
        }
