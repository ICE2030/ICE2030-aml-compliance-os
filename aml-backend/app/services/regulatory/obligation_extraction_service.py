"""Obligation Extraction Service - identifies regulatory obligations from provisions."""
import re
import logging
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.source import Provision
from app.models.regulatory.obligation import (
    Obligation, ObligationType, ExtractionMethod, ReviewStatus,
)

logger = logging.getLogger(__name__)


class ExtractedObligation:
    """An obligation extracted from text."""
    def __init__(self, text: str, obligation_type: str, confidence: float,
                 normalized_summary: str = None, condition: str = None,
                 deadline: str = None, applies_to: list = None,
                 extraction_method: str = "rule_based"):
        self.text = text
        self.obligation_type = obligation_type
        self.confidence = confidence
        self.normalized_summary = normalized_summary or text[:200]
        self.condition = condition
        self.deadline = deadline
        self.applies_to = applies_to or []
        self.extraction_method = extraction_method


class RuleBasedExtractor:
    """Rule-based obligation extraction using pattern matching."""

    # Mandatory obligation patterns (English + Arabic)
    MANDATORY_PATTERNS = [
        (r'\b(?:shall|must|is required to|are required to|is obligated|are obligated)\b[^.]{10,200}\.', 'mandatory', 0.85),
        (r'\b(?:shall not|must not|is prohibited|are prohibited|may not)\b[^.]{10,200}\.', 'prohibition', 0.85),
        (r'\b(?:يجب|يلتزم|يتعين|ملزم)\b[^.。]{10,200}[.。]', 'mandatory', 0.80),
        (r'\b(?:يحظر|لا يجوز|يمنع|ممنوع)\b[^.。]{10,200}[.。]', 'prohibition', 0.80),
    ]

    # Reporting / deadline patterns
    REPORTING_PATTERNS = [
        (r'\b(?:report|notify|inform|submit|file|disclose)\b[^.]{10,200}\.', 'reporting', 0.75),
        (r'\b(?:within \d+ (?:days?|hours?|months?|business days?))\b[^.]{5,200}\.', 'deadline', 0.80),
        (r'\b(?:إبلاغ|تقديم|إخطار|تقرير)\b[^.。]{10,200}[.。]', 'reporting', 0.75),
        (r'\b(?:خلال \d+ (?:أيام?|ساعات?|أشهر?))\b[^.。]{5,200}[.。]', 'deadline', 0.75),
    ]

    # Threshold patterns
    THRESHOLD_PATTERNS = [
        (r'\b(?:exceed|exceeding|above|more than|at least|minimum|maximum)\s+(?:SAR|USD|EUR|£|\$|ر\.س)?\s*[\d,]+', 'threshold', 0.80),
        (r'\b(?:تجاوز|يتجاوز|أكثر من|الحد الأدنى|الحد الأقصى)\s+[\d,]+', 'threshold', 0.75),
    ]

    # Governance patterns
    GOVERNANCE_PATTERNS = [
        (r'\b(?:board|senior management|compliance officer|MLRO|designated officer)\b[^.]{10,200}(?:shall|must|responsible)[^.]{5,200}\.', 'governance', 0.75),
        (r'\b(?:مجلس الإدارة|الإدارة العليا|مسؤول الالتزام|المسؤول المعين)\b[^.。]{10,200}[.。]', 'governance', 0.70),
    ]

    # Entity type patterns for applies_to
    ENTITY_PATTERNS = {
        "bank": r'\b(?:bank|banks|banking|مصرف|بنك|بنوك)\b',
        "fintech": r'\b(?:fintech|financial technology|تقنية مالية|فنتك)\b',
        "insurance": r'\b(?:insurance|insurer|تأمين|شركة تأمين)\b',
        "securities": r'\b(?:securities|broker|dealer|أوراق مالية|وسيط)\b',
        "exchange": r'\b(?:exchange house|money exchange|صرافة|محل صرافة)\b',
        "crowdfunding": r'\b(?:crowdfunding|crowd-funding|تمويل جماعي)\b',
        "payment": r'\b(?:payment service|e-wallet|digital wallet|خدمة دفع|محفظة إلكترونية)\b',
        "all_financial": r'\b(?:financial institution|regulated entity|المنشأة المالية|الجهة الخاضعة)\b',
    }

    @staticmethod
    def extract(text: str) -> list[ExtractedObligation]:
        """Extract obligations from text using rule-based patterns."""
        obligations = []
        seen_texts = set()

        all_patterns = (
            RuleBasedExtractor.MANDATORY_PATTERNS +
            RuleBasedExtractor.REPORTING_PATTERNS +
            RuleBasedExtractor.THRESHOLD_PATTERNS +
            RuleBasedExtractor.GOVERNANCE_PATTERNS
        )

        for pattern, ob_type, confidence in all_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                matched_text = match.group(0).strip()
                # Deduplicate
                text_key = matched_text[:100].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)

                # Detect entity types
                applies_to = []
                for entity_type, entity_pattern in RuleBasedExtractor.ENTITY_PATTERNS.items():
                    if re.search(entity_pattern, matched_text, re.IGNORECASE):
                        applies_to.append(entity_type)

                # Extract deadline if present
                deadline = None
                deadline_match = re.search(r'within (\d+ (?:days?|hours?|months?|business days?))', matched_text, re.IGNORECASE)
                if deadline_match:
                    deadline = deadline_match.group(1)
                deadline_match_ar = re.search(r'خلال (\d+ (?:أيام?|ساعات?|أشهر?))', matched_text)
                if deadline_match_ar:
                    deadline = deadline_match_ar.group(1)

                # Extract condition if present
                condition = None
                condition_match = re.search(r'(?:if|when|where|in case|provided that)\s+([^,\.]+)', matched_text, re.IGNORECASE)
                if condition_match:
                    condition = condition_match.group(1).strip()

                obligations.append(ExtractedObligation(
                    text=matched_text,
                    obligation_type=ob_type,
                    confidence=confidence,
                    normalized_summary=matched_text[:200],
                    condition=condition,
                    deadline=deadline,
                    applies_to=applies_to if applies_to else ["all_financial"],
                    extraction_method="rule_based",
                ))

        return obligations


class ObligationExtractionService:
    """Manages obligation extraction from regulatory provisions."""

    @staticmethod
    async def extract_from_provision(
        db: AsyncSession,
        provision_id: str,
    ) -> list[Obligation]:
        """Extract obligations from a single provision."""
        provision = await db.get(Provision, provision_id)
        if not provision:
            return []

        extracted = RuleBasedExtractor.extract(provision.text)

        obligations = []
        for ext in extracted:
            try:
                ob_type = ObligationType(ext.obligation_type)
            except (ValueError, KeyError):
                ob_type = ObligationType.MANDATORY

            ob = Obligation(
                provision_id=provision_id,
                text=ext.text,
                normalized_summary=ext.normalized_summary,
                obligation_type=ob_type,
                applies_to_entity_types=ext.applies_to,
                condition=ext.condition,
                deadline=ext.deadline,
                confidence=ext.confidence,
                extraction_method=ExtractionMethod.RULE_BASED,
                review_status=ReviewStatus.PENDING,
            )
            db.add(ob)
            obligations.append(ob)

        await db.flush()
        return obligations

    @staticmethod
    async def extract_from_document(db: AsyncSession, document_id: str) -> list[Obligation]:
        """Extract obligations from all provisions in a document."""
        provisions = await db.execute(
            select(Provision).where(Provision.document_id == document_id)
        )
        all_obligations = []
        for prov in provisions.scalars().all():
            obs = await ObligationExtractionService.extract_from_provision(db, prov.id)
            all_obligations.extend(obs)
        return all_obligations

    @staticmethod
    async def get_obligations(
        db: AsyncSession,
        obligation_type: str = None,
        review_status: str = None,
        min_confidence: float = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Obligation], int]:
        """Get obligations with filters."""
        q = select(Obligation)
        count_q = select(func.count(Obligation.id))

        if obligation_type:
            q = q.where(Obligation.obligation_type == obligation_type)
            count_q = count_q.where(Obligation.obligation_type == obligation_type)
        if review_status:
            q = q.where(Obligation.review_status == review_status)
            count_q = count_q.where(Obligation.review_status == review_status)
        if min_confidence is not None:
            q = q.where(Obligation.confidence >= min_confidence)
            count_q = count_q.where(Obligation.confidence >= min_confidence)

        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(q.order_by(Obligation.created_at.desc()).offset(skip).limit(limit))
        return list(result.scalars().all()), total

    @staticmethod
    async def review_obligation(
        db: AsyncSession,
        obligation_id: str,
        decision: str,
        reviewer_notes: str = None,
        confidence_adjustment: float = None,
    ) -> Optional[Obligation]:
        """Review an extracted obligation."""
        ob = await db.get(Obligation, obligation_id)
        if not ob:
            return None

        try:
            ob.review_status = ReviewStatus(decision)
        except (ValueError, KeyError):
            ob.review_status = ReviewStatus.PENDING

        if reviewer_notes:
            ob.reviewer_notes = reviewer_notes
        if confidence_adjustment is not None:
            ob.confidence = confidence_adjustment

        await db.flush()
        return ob

    @staticmethod
    async def get_obligation_stats(db: AsyncSession) -> dict:
        """Get obligation extraction statistics."""
        total = (await db.execute(select(func.count(Obligation.id)))).scalar() or 0
        pending = (await db.execute(
            select(func.count(Obligation.id)).where(Obligation.review_status == ReviewStatus.PENDING)
        )).scalar() or 0
        approved = (await db.execute(
            select(func.count(Obligation.id)).where(Obligation.review_status == ReviewStatus.APPROVED)
        )).scalar() or 0

        by_type = {}
        type_result = await db.execute(
            select(Obligation.obligation_type, func.count(Obligation.id))
            .group_by(Obligation.obligation_type)
        )
        for row in type_result.all():
            by_type[row[0]] = row[1]

        avg_confidence = (await db.execute(
            select(func.avg(Obligation.confidence))
        )).scalar() or 0.0

        return {
            "total_obligations": total,
            "pending_review": pending,
            "approved": approved,
            "by_type": by_type,
            "average_confidence": round(float(avg_confidence), 2),
        }
