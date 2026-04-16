"""Change Detection Service - monitors sources for updates and classifies impact."""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.source import Source, SourceVersion, SourceStatus
from app.models.regulatory.change import ChangeEvent, ChangeType, ImpactLevel

logger = logging.getLogger(__name__)


class ChangeDetectionService:
    """Detects and classifies changes in regulatory sources."""

    # Keywords that indicate high-impact changes
    MATERIAL_KEYWORDS = [
        "penalty", "fine", "prohibition", "ban", "revoke", "suspend",
        "mandatory", "shall", "must", "required", "obligation",
        "عقوبة", "غرامة", "حظر", "إلزامي", "يجب",
    ]
    OPERATIONAL_KEYWORDS = [
        "deadline", "reporting", "filing", "notification", "submit",
        "procedure", "process", "timeline", "within",
        "موعد", "تقرير", "إخطار", "تقديم", "إجراء",
    ]

    @staticmethod
    async def detect_changes(db: AsyncSession, source_id: str) -> Optional[ChangeEvent]:
        """Compare current and previous versions to detect changes."""
        versions = await db.execute(
            select(SourceVersion)
            .where(SourceVersion.source_id == source_id)
            .order_by(SourceVersion.version_number.desc())
            .limit(2)
        )
        versions_list = list(versions.scalars().all())

        if len(versions_list) < 2:
            # First version or no versions - check if it's new
            if len(versions_list) == 1:
                event = ChangeEvent(
                    source_id=source_id,
                    new_version_id=versions_list[0].id,
                    detected_at=datetime.now(timezone.utc),
                    change_type=ChangeType.NEW_DOCUMENT,
                    impact_level=ImpactLevel.INFORMATIONAL,
                    summary="New source version ingested",
                    review_status="pending",
                )
                db.add(event)
                await db.flush()
                return event
            return None

        new_version = versions_list[0]
        old_version = versions_list[1]

        if new_version.content_hash == old_version.content_hash:
            return None  # No change

        # Detect what changed
        change_type, summary = ChangeDetectionService._classify_change(
            old_version.raw_content or "",
            new_version.raw_content or "",
        )

        # Classify impact
        impact_level = ChangeDetectionService._classify_impact(
            new_version.raw_content or "",
            summary,
        )

        event = ChangeEvent(
            source_id=source_id,
            old_version_id=old_version.id,
            new_version_id=new_version.id,
            detected_at=datetime.now(timezone.utc),
            change_type=change_type,
            impact_level=impact_level,
            summary=summary,
            review_status="pending",
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    def _classify_change(old_content: str, new_content: str) -> tuple[ChangeType, str]:
        """Classify the type of change between two versions."""
        if not old_content:
            return ChangeType.NEW_DOCUMENT, "New document added"

        old_lines = set(old_content.splitlines())
        new_lines = set(new_content.splitlines())

        added = new_lines - old_lines
        removed = old_lines - new_lines

        if not removed and added:
            return ChangeType.SECTION_ADDED, f"Content added: {len(added)} new lines"
        elif removed and not added:
            return ChangeType.SECTION_REMOVED, f"Content removed: {len(removed)} lines removed"
        elif removed and added:
            return ChangeType.CONTENT_MODIFIED, f"Content modified: {len(added)} lines added, {len(removed)} lines removed"
        else:
            return ChangeType.METADATA_CHANGED, "Metadata or formatting changed"

    @staticmethod
    def _classify_impact(content: str, change_summary: str) -> ImpactLevel:
        """Classify the impact level of a change."""
        text = (content + " " + change_summary).lower()

        # Check for material impact keywords
        material_count = sum(1 for kw in ChangeDetectionService.MATERIAL_KEYWORDS if kw.lower() in text)
        if material_count >= 2:
            return ImpactLevel.MATERIAL

        # Check for operational impact keywords
        operational_count = sum(1 for kw in ChangeDetectionService.OPERATIONAL_KEYWORDS if kw.lower() in text)
        if operational_count >= 2:
            return ImpactLevel.OPERATIONAL

        if material_count >= 1 or operational_count >= 1:
            return ImpactLevel.INTERPRETIVE

        return ImpactLevel.INFORMATIONAL

    @staticmethod
    async def get_recent_changes(
        db: AsyncSession,
        source_id: str = None,
        impact_level: str = None,
        review_status: str = None,
        limit: int = 50,
    ) -> list[ChangeEvent]:
        """Get recent change events with optional filters."""
        q = select(ChangeEvent)
        if source_id:
            q = q.where(ChangeEvent.source_id == source_id)
        if impact_level:
            q = q.where(ChangeEvent.impact_level == impact_level)
        if review_status:
            q = q.where(ChangeEvent.review_status == review_status)
        q = q.order_by(ChangeEvent.detected_at.desc()).limit(limit)
        result = await db.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def review_change(
        db: AsyncSession,
        change_id: str,
        reviewer: str,
        status: str = "reviewed",
    ) -> Optional[ChangeEvent]:
        """Mark a change event as reviewed."""
        event = await db.get(ChangeEvent, change_id)
        if not event:
            return None
        event.review_status = status
        event.reviewed_by = reviewer
        event.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        return event

    @staticmethod
    async def get_change_stats(db: AsyncSession) -> dict:
        """Get change detection statistics."""
        total = (await db.execute(select(func.count(ChangeEvent.id)))).scalar() or 0
        pending = (await db.execute(
            select(func.count(ChangeEvent.id)).where(ChangeEvent.review_status == "pending")
        )).scalar() or 0

        by_impact = {}
        impact_result = await db.execute(
            select(ChangeEvent.impact_level, func.count(ChangeEvent.id))
            .group_by(ChangeEvent.impact_level)
        )
        for row in impact_result.all():
            by_impact[row[0]] = row[1]

        by_type = {}
        type_result = await db.execute(
            select(ChangeEvent.change_type, func.count(ChangeEvent.id))
            .group_by(ChangeEvent.change_type)
        )
        for row in type_result.all():
            by_type[row[0]] = row[1]

        return {
            "total_changes": total,
            "pending_review": pending,
            "by_impact": by_impact,
            "by_type": by_type,
        }
