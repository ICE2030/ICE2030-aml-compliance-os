"""Obligation Extraction Service - identifies regulatory obligations from provisions.

Hardened version with:
- Priority 1: Full-sentence threshold extraction (no fragment extraction)
- Priority 4: Penalty provision classification (separate from operational obligations)
- Priority 5: Improved CDD/identification/verification/beneficial ownership extraction
"""
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


# ── Helpers ──────────────────────────────────────────────────────────

def _get_governing_sentence(text: str, match_start: int, match_end: int) -> str:
    """Return the full sentence that contains the matched span.

    Walks backward to the previous period (.) or start-of-text
    and forward to the next period (.) or end-of-text.
    Does NOT treat semicolons as sentence boundaries because regulatory
    text uses semicolons to separate list items within a single sentence
    (e.g., "apply CDD when: (a) ...; (b) ...; (c) ...").
    Ensures threshold/trigger phrases are never extracted in isolation.
    """
    sent_start = match_start
    while sent_start > 0 and text[sent_start - 1] != '.':
        sent_start -= 1
    sent_end = match_end
    while sent_end < len(text) and text[sent_end] != '.':
        sent_end += 1
    if sent_end < len(text):
        sent_end += 1
    sentence = text[sent_start:sent_end].strip()
    sentence = re.sub(r'^[.;,\s]+', '', sentence).strip()
    return sentence


def _normalize_summary(text: str, obligation_type: str) -> str:
    """Generate a concise normalized summary from the obligation text."""
    summary = text.strip()
    if len(summary) > 250:
        for sep in ['; ', ', ', ' — ', ' - ']:
            idx = summary.find(sep, 100)
            if 100 < idx < 250:
                summary = summary[:idx]
                break
        else:
            summary = summary[:250].rsplit(' ', 1)[0] + '...'
    return summary


class ExtractedObligation:
    """An obligation extracted from text."""
    def __init__(self, text: str, obligation_type: str, confidence: float,
                 normalized_summary: str = None, condition: str = None,
                 deadline: str = None, applies_to: list = None,
                 extraction_method: str = "rule_based"):
        self.text = text
        self.obligation_type = obligation_type
        self.confidence = confidence
        self.normalized_summary = normalized_summary or _normalize_summary(text, obligation_type)
        self.condition = condition
        self.deadline = deadline
        self.applies_to = applies_to or []
        self.extraction_method = extraction_method


class RuleBasedExtractor:
    """Rule-based obligation extraction using pattern matching.

    Hardened patterns:
    - Threshold: full governing sentence, not just the numeric value
    - Penalty: classified separately from operational obligations
    - CDD: identification, verification, beneficial ownership, ongoing monitoring
    """

    # ── Penalty / enforcement language (used for filtering) ──────────
    PENALTY_LANGUAGE_RE = re.compile(
        r'\b(?:sentenced?|convicted?|punished?|penalt(?:y|ies)|imprisonment|'
        r'fine[sd]?|confiscat(?:e|ed|ion)|years? in (?:prison|jail)|'
        r'عقوبة|حبس|سجن|غرامة|مصادرة|يعاقب)\b',
        re.IGNORECASE,
    )

    # ── Mandatory / Prohibition ──────────────────────────────────────
    MANDATORY_PATTERNS = [
        (r'\b(?:shall|must|is required to|are required to|is obligated|are obligated)\b[^.]{10,200}\.', 'mandatory', 0.85),
        (r'\b(?:shall not|must not|is prohibited|are prohibited|may not)\b[^.]{10,200}\.', 'prohibition', 0.85),
        (r'\b(?:يجب|يلتزم|يتعين|ملزم)\b[^.。]{10,200}[.。]', 'mandatory', 0.80),
        (r'\b(?:يحظر|لا يجوز|يمنع|ممنوع)\b[^.。]{10,200}[.。]', 'prohibition', 0.80),
    ]

    # ── Reporting / Deadline ─────────────────────────────────────────
    REPORTING_PATTERNS = [
        (r'\b(?:report|notify|inform|submit|file|disclose)\b[^.]{10,200}\.', 'reporting', 0.75),
        (r'\b(?:within \d+ (?:days?|hours?|months?|business days?))\b[^.]{5,200}\.', 'deadline', 0.80),
        (r'\b(?:إبلاغ|تقديم|إخطار|تقرير)\b[^.。]{10,200}[.。]', 'reporting', 0.75),
        (r'\b(?:خلال \d+ (?:أيام?|ساعات?|أشهر?))\b[^.。]{5,200}[.。]', 'deadline', 0.75),
    ]

    # ── Threshold triggers (P1: context-aware, no fragment match) ────
    THRESHOLD_TRIGGER_PATTERNS = [
        r'\b(?:exceed|exceeding|above|more than|at least|minimum|maximum)\s+(?:SAR|USD|EUR|£|\$|ر\.س)?\s*[\d,]+',
        r'\b(?:تجاوز|يتجاوز|أكثر من|الحد الأدنى|الحد الأقصى)\s+[\d,]+',
    ]
    THRESHOLD_CONFIDENCE = 0.80

    # ── Penalty (P4: separate classification) ────────────────────────
    PENALTY_PATTERNS = [
        (r'\b(?:sentenced?|convicted?|punished?|penalt(?:y|ies)|imprisonment|fine|confiscat)\b[^.]{10,300}\.', 'penalty', 0.80),
        (r'\b(?:عقوبة|حبس|سجن|غرامة|مصادرة|يعاقب)\b[^.。]{10,300}[.。]', 'penalty', 0.75),
    ]

    # ── Governance ───────────────────────────────────────────────────
    GOVERNANCE_PATTERNS = [
        (r'\b(?:board|senior management|compliance officer|MLRO|designated officer)\b[^.]{10,200}(?:shall|must|responsible)[^.]{5,200}\.', 'governance', 0.75),
        (r'\b(?:مجلس الإدارة|الإدارة العليا|مسؤول الالتزام|المسؤول المعين)\b[^.。]{10,200}[.。]', 'governance', 0.70),
    ]

    # ── CDD / Identification / Verification (P5: new patterns) ──────
    CDD_PATTERNS = [
        (r'\b(?:identify|identifying)\s+(?:the\s+)?(?:customer|client|applicant|beneficial owner)[^.]{5,200}\.', 'identification', 0.85),
        (r'\b(?:verif(?:y|ying|ication))\s+(?:the\s+)?(?:customer|client|identity|identities|that customer)[^.]{5,200}\.', 'verification', 0.85),
        (r'\b(?:beneficial\s+owner(?:ship)?)\b[^.]{10,200}(?:identify|determine|verify|establish|reasonable measures)[^.]{5,200}\.', 'identification', 0.85),
        (r'\b(?:customer\s+due\s+diligence|CDD)\s+measures?\b[^.]{10,200}\.', 'mandatory', 0.85),
        (r'\b(?:ongoing\s+(?:due\s+diligence|monitoring|scrutiny))\b[^.]{10,200}\.', 'ongoing_monitoring', 0.80),
        (r'\b(?:maintain|keep|retain)\s+(?:all\s+)?(?:records?|documentation)\b[^.]{10,200}\.', 'recordkeeping', 0.80),
        (r'(?:should be|shall be|are|is)\s+required\s+to\s+(?:undertake|conduct|perform|carry out)\s+(?:customer\s+due\s+diligence|CDD)[^.]{5,200}\.', 'mandatory', 0.85),
        # Arabic CDD
        (r'\b(?:التعرف على|تحديد هوية|التحقق من هوية)\b[^.。]{10,200}[.。]', 'identification', 0.80),
        (r'\b(?:المستفيد الحقيقي|المالك المستفيد)\b[^.。]{10,200}[.。]', 'identification', 0.80),
    ]

    # ── Entity type patterns for applies_to ──────────────────────────
    ENTITY_PATTERNS = {
        "bank": r'\b(?:bank|banks|banking|مصرف|بنك|بنوك)\b',
        "fintech": r'\b(?:fintech|financial technology|تقنية مالية|فنتك)\b',
        "insurance": r'\b(?:insurance|insurer|reinsurance|تأمين|شركة تأمين)\b',
        "securities": r'\b(?:securities|broker|dealer|أوراق مالية|وسيط)\b',
        "exchange": r'\b(?:exchange house|money exchange|صرافة|محل صرافة)\b',
        "crowdfunding": r'\b(?:crowdfunding|crowd-funding|تمويل جماعي)\b',
        "payment": r'\b(?:payment service|e-wallet|digital wallet|خدمة دفع|محفظة إلكترونية)\b',
        "finance_company": r'\b(?:finance compan(?:y|ies))\b',
        "dnfbp": r'\b(?:designated non-financial|DNFBPs?)\b',
        "all_financial": r'\b(?:financial institution|regulated entity|المنشأة المالية|الجهة الخاضعة|all FIs)\b',
    }

    MIN_OBLIGATION_LENGTH = 30

    @staticmethod
    def extract(text: str) -> list[ExtractedObligation]:
        """Extract obligations from text using rule-based patterns.

        Priority 1: Thresholds are expanded to full governing sentences.
        Priority 4: Penalty provisions are classified separately.
        Priority 5: CDD/identification/verification patterns added.
        """
        obligations: list[ExtractedObligation] = []
        seen_texts: set[str] = set()

        # --- Phase A: Penalty detection (P4) — run first so we can skip overlap ---
        penalty_spans: set[tuple[int, int]] = set()
        for pattern, ob_type, confidence in RuleBasedExtractor.PENALTY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                penalty_spans.add((match.start(), match.end()))
                matched_text = match.group(0).strip()
                text_key = matched_text[:100].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)
                if len(matched_text) < RuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue
                applies_to = RuleBasedExtractor._detect_entities(matched_text)
                obligations.append(ExtractedObligation(
                    text=matched_text,
                    obligation_type='penalty',
                    confidence=confidence,
                    condition=RuleBasedExtractor._extract_condition(matched_text),
                    applies_to=applies_to if applies_to else ["all_financial"],
                ))

        # --- Phase B: Standard patterns (mandatory, prohibition, reporting, governance, CDD) ---
        standard_patterns = (
            RuleBasedExtractor.MANDATORY_PATTERNS +
            RuleBasedExtractor.REPORTING_PATTERNS +
            RuleBasedExtractor.GOVERNANCE_PATTERNS +
            RuleBasedExtractor.CDD_PATTERNS
        )

        for pattern, ob_type, confidence in standard_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                matched_text = match.group(0).strip()

                # Skip if this overlaps with a penalty span (any overlap, not just containment)
                if any(match.start() < ps[1] and match.end() > ps[0] for ps in penalty_spans):
                    continue

                text_key = matched_text[:100].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)

                if len(matched_text) < RuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue

                # Reclassify as penalty if the text contains penalty language
                final_type = ob_type
                if ob_type in ('mandatory', 'prohibition') and RuleBasedExtractor.PENALTY_LANGUAGE_RE.search(matched_text):
                    final_type = 'penalty'

                applies_to = RuleBasedExtractor._detect_entities(matched_text)
                condition = RuleBasedExtractor._extract_condition(matched_text)
                deadline = RuleBasedExtractor._extract_deadline(matched_text)

                obligations.append(ExtractedObligation(
                    text=matched_text,
                    obligation_type=final_type,
                    confidence=confidence,
                    condition=condition,
                    deadline=deadline,
                    applies_to=applies_to if applies_to else ["all_financial"],
                ))

        # --- Phase C: Threshold extraction with full-sentence context (P1) ---
        for trigger_pattern in RuleBasedExtractor.THRESHOLD_TRIGGER_PATTERNS:
            for match in re.finditer(trigger_pattern, text, re.IGNORECASE | re.MULTILINE):
                governing = _get_governing_sentence(text, match.start(), match.end())

                if len(governing) < RuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue
                text_key = governing[:100].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)

                if any(ps[0] <= match.start() <= ps[1] for ps in penalty_spans):
                    continue

                applies_to = RuleBasedExtractor._detect_entities(governing)
                condition = RuleBasedExtractor._extract_condition(governing)

                obligations.append(ExtractedObligation(
                    text=governing,
                    obligation_type='threshold',
                    confidence=RuleBasedExtractor.THRESHOLD_CONFIDENCE,
                    condition=condition,
                    applies_to=applies_to if applies_to else ["all_financial"],
                ))

        # --- Phase D: Deduplicate overlapping obligations ---
        # When multiple patterns match the same (or substantially overlapping)
        # text, keep the one with the more specific obligation type.
        obligations = RuleBasedExtractor._deduplicate_overlapping(obligations)

        return obligations

    @staticmethod
    def _deduplicate_overlapping(
        obligations: list["ExtractedObligation"],
    ) -> list["ExtractedObligation"]:
        """Merge obligations whose text is a substring of another's.

        When two obligations share >=80% of their text (by token overlap),
        keep the one with the more specific type. Type specificity order:
        penalty > identification > verification > ongoing_monitoring >
        recordkeeping > threshold > governance > reporting > deadline >
        prohibition > mandatory.
        """
        TYPE_SPECIFICITY = {
            'penalty': 11, 'identification': 10, 'verification': 9,
            'ongoing_monitoring': 8, 'recordkeeping': 7, 'threshold': 6,
            'governance': 5, 'reporting': 4, 'deadline': 3,
            'prohibition': 2, 'mandatory': 1,
        }
        if len(obligations) <= 1:
            return obligations

        # Build token sets for cheap overlap check
        token_sets = []
        for ob in obligations:
            tokens = set(re.findall(r'\w+', ob.text.lower()))
            token_sets.append(tokens)

        to_remove: set[int] = set()
        for i in range(len(obligations)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(obligations)):
                if j in to_remove:
                    continue
                overlap = len(token_sets[i] & token_sets[j])
                union = len(token_sets[i] | token_sets[j]) or 1
                if overlap / union >= 0.80:  # Jaccard similarity — truly same text
                    # Keep the more specific one
                    spec_i = TYPE_SPECIFICITY.get(obligations[i].obligation_type, 0)
                    spec_j = TYPE_SPECIFICITY.get(obligations[j].obligation_type, 0)
                    if spec_i >= spec_j:
                        to_remove.add(j)
                    else:
                        to_remove.add(i)
                        break  # i is removed, stop comparing

        return [ob for idx, ob in enumerate(obligations) if idx not in to_remove]

    @staticmethod
    def _detect_entities(text: str) -> list[str]:
        """Detect entity types mentioned in the text."""
        entities = []
        for entity_type, pattern in RuleBasedExtractor.ENTITY_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                entities.append(entity_type)
        return entities

    @staticmethod
    def _extract_condition(text: str) -> Optional[str]:
        """Extract conditional clause from obligation text."""
        match = re.search(
            r'(?:if|when|where|in case|provided that|unless)\s+([^,\.]{5,150})',
            text, re.IGNORECASE
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_deadline(text: str) -> Optional[str]:
        """Extract deadline from obligation text."""
        match = re.search(
            r'within (\d+ (?:days?|hours?|months?|years?|business days?))',
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)
        match_ar = re.search(r'خلال (\d+ (?:أيام?|ساعات?|أشهر?))', text)
        if match_ar:
            return match_ar.group(1)
        match2 = re.search(
            r'(?:minimum of|at least)\s+(\d+\s+(?:years?|months?|days?))',
            text, re.IGNORECASE
        )
        if match2:
            return match2.group(1)
        return None


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
