"""Review Queue Service — manages human validation workflow for extracted obligations.

Supports:
- Listing obligations pending review with filters
- Approving/rejecting obligations with notes
- Tracking review decisions with audit trail
- Statistics on review progress
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.obligation import (
    Obligation, ObligationType, ExtractionMethod, ReviewStatus,
)
from app.models.regulatory.change import ReviewDecision, ReviewDecisionType
from app.models.regulatory.source import Provision, RegulatoryDocument, Regulator, Jurisdiction

logger = logging.getLogger(__name__)


class ReviewQueueService:
    """Manages the obligation review queue."""

    @staticmethod
    async def get_queue(
        db: AsyncSession,
        review_status: Optional[str] = None,
        obligation_type: Optional[str] = None,
        regulator_filter: Optional[str] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        extraction_method: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """Get obligations in the review queue with full provenance context.

        Returns a tuple of (items, total_count).
        Each item includes obligation data plus source/regulator/jurisdiction context.
        """
        # Base query
        q = select(Obligation)
        count_q = select(func.count(Obligation.id))

        # Apply filters
        if review_status:
            try:
                status = ReviewStatus(review_status)
                q = q.where(Obligation.review_status == status)
                count_q = count_q.where(Obligation.review_status == status)
            except (ValueError, KeyError):
                pass

        if obligation_type:
            try:
                ob_type = ObligationType(obligation_type)
                q = q.where(Obligation.obligation_type == ob_type)
                count_q = count_q.where(Obligation.obligation_type == ob_type)
            except (ValueError, KeyError):
                pass

        if extraction_method:
            try:
                method = ExtractionMethod(extraction_method)
                q = q.where(Obligation.extraction_method == method)
                count_q = count_q.where(Obligation.extraction_method == method)
            except (ValueError, KeyError):
                pass

        if min_confidence is not None:
            q = q.where(Obligation.confidence >= min_confidence)
            count_q = count_q.where(Obligation.confidence >= min_confidence)

        if max_confidence is not None:
            q = q.where(Obligation.confidence <= max_confidence)
            count_q = count_q.where(Obligation.confidence <= max_confidence)

        total = (await db.execute(count_q)).scalar() or 0

        # Fetch obligations with ordering
        result = await db.execute(
            q.order_by(Obligation.confidence.asc(), Obligation.created_at.desc())
            .offset(skip).limit(limit)
        )
        obligations = list(result.scalars().all())

        # Enrich with provenance context
        items = []
        for ob in obligations:
            item = {
                "id": ob.id,
                "text": ob.text,
                "text_ar": ob.text_ar,
                "normalized_summary": ob.normalized_summary,
                "normalized_summary_ar": ob.normalized_summary_ar,
                "obligation_type": ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type),
                "applies_to_entity_types": ob.applies_to_entity_types,
                "applies_to_product_types": ob.applies_to_product_types,
                "condition": ob.condition,
                "deadline": ob.deadline,
                "confidence": ob.confidence,
                "extraction_method": ob.extraction_method.value if hasattr(ob.extraction_method, 'value') else str(ob.extraction_method),
                "review_status": ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status),
                "reviewer_notes": ob.reviewer_notes,
                "version": ob.version,
                "is_active": ob.is_active,
                "created_at": ob.created_at.isoformat() if ob.created_at else None,
            }

            # Enrich with provision/source context
            provision = await db.get(Provision, ob.provision_id)
            if provision:
                item["provision_id"] = provision.id
                item["provision_section"] = provision.section_number
                item["provision_title"] = provision.title
                item["provision_title_ar"] = provision.title_ar

                doc = await db.get(RegulatoryDocument, provision.document_id)
                if doc:
                    regulator = await db.get(Regulator, doc.regulator_id)
                    jurisdiction = await db.get(Jurisdiction, doc.jurisdiction_id)
                    item["regulator_name"] = regulator.name if regulator else None
                    item["regulator_abbreviation"] = regulator.abbreviation if regulator else None
                    item["jurisdiction_name"] = jurisdiction.name if jurisdiction else None
                    item["jurisdiction_code"] = jurisdiction.code if jurisdiction else None

            # Filter by regulator if specified (post-fetch filter since join is complex)
            if regulator_filter:
                if item.get("regulator_abbreviation") != regulator_filter:
                    total -= 1  # Adjust count
                    continue

            items.append(item)

        return items, total

    @staticmethod
    async def review_obligation(
        db: AsyncSession,
        obligation_id: str,
        decision: str,
        reviewer_notes: Optional[str] = None,
        confidence_adjustment: Optional[float] = None,
        reviewer_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Submit a review decision for an obligation.

        Creates a ReviewDecision audit record and updates the obligation status.
        """
        ob = await db.get(Obligation, obligation_id)
        if not ob:
            return None

        # Map decision to ReviewStatus
        status_map = {
            "approved": ReviewStatus.APPROVED,
            "rejected": ReviewStatus.REJECTED,
            "needs_revision": ReviewStatus.NEEDS_REVISION,
        }
        new_status = status_map.get(decision)
        if not new_status:
            return None

        # Update obligation
        ob.review_status = new_status
        if reviewer_notes:
            ob.reviewer_notes = reviewer_notes
        if confidence_adjustment is not None:
            ob.confidence = confidence_adjustment
        ob.version += 1

        # Create review decision audit record
        decision_type_map = {
            "approved": ReviewDecisionType.APPROVED,
            "rejected": ReviewDecisionType.REJECTED,
            "needs_revision": ReviewDecisionType.NEEDS_REVISION,
        }
        review_decision = ReviewDecision(
            content_type="obligation",
            content_id=obligation_id,
            reviewer_id=reviewer_id,
            decision=decision_type_map[decision],
            confidence_adjustment=confidence_adjustment,
            notes=reviewer_notes,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review_decision)
        await db.flush()

        return {
            "id": ob.id,
            "review_status": ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status),
            "reviewer_notes": ob.reviewer_notes,
            "confidence": ob.confidence,
            "version": ob.version,
            "decision_recorded": True,
        }

    @staticmethod
    async def get_review_stats(db: AsyncSession) -> dict:
        """Get review queue statistics."""
        total = (await db.execute(select(func.count(Obligation.id)))).scalar() or 0

        # Count by status
        status_counts = {}
        for status in ReviewStatus:
            count = (await db.execute(
                select(func.count(Obligation.id)).where(Obligation.review_status == status)
            )).scalar() or 0
            status_counts[status.value] = count

        # Count by type
        type_counts = {}
        type_result = await db.execute(
            select(Obligation.obligation_type, func.count(Obligation.id))
            .group_by(Obligation.obligation_type)
        )
        for row in type_result.all():
            ob_type = row[0].value if hasattr(row[0], 'value') else str(row[0])
            type_counts[ob_type] = row[1]

        # Count by extraction method
        method_counts = {}
        method_result = await db.execute(
            select(Obligation.extraction_method, func.count(Obligation.id))
            .group_by(Obligation.extraction_method)
        )
        for row in method_result.all():
            method = row[0].value if hasattr(row[0], 'value') else str(row[0])
            method_counts[method] = row[1]

        # Average confidence
        avg_confidence = (await db.execute(
            select(func.avg(Obligation.confidence))
        )).scalar() or 0.0

        # Review decisions count
        total_decisions = (await db.execute(
            select(func.count(ReviewDecision.id))
        )).scalar() or 0

        return {
            "total_obligations": total,
            "by_status": status_counts,
            "by_type": type_counts,
            "by_extraction_method": method_counts,
            "average_confidence": round(float(avg_confidence), 2),
            "total_review_decisions": total_decisions,
        }

    @staticmethod
    async def batch_review(
        db: AsyncSession,
        obligation_ids: list[str],
        decision: str,
        reviewer_notes: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> dict:
        """Batch review multiple obligations at once."""
        results = {"reviewed": 0, "failed": 0, "ids": []}
        for ob_id in obligation_ids:
            result = await ReviewQueueService.review_obligation(
                db, ob_id, decision, reviewer_notes, reviewer_id=reviewer_id,
            )
            if result:
                results["reviewed"] += 1
                results["ids"].append(ob_id)
            else:
                results["failed"] += 1
        return results
