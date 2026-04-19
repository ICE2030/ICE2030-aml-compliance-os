"""Phase 5A Services: Improved Extraction, Control Suggestions, Evidence Expiry Alerts.

1. Improved Obligation Extraction — better classification, dedup, applicability, AR/EN consistency
2. Automated Control Suggestions — generate suggested controls from obligation text
3. Evidence Expiry Alerts — surface expired and soon-to-expire evidence
"""
import re
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.obligation import (
    Obligation, Control, ObligationControl, EvidenceArtifact,
    ObligationType, ExtractionMethod, ReviewStatus,
    ControlType, ControlStatus,
)
from app.models.regulatory.source import (
    Provision, RegulatoryDocument, Regulator, Jurisdiction,
)
from app.models.base import generate_uuid

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 1. Improved Obligation Extraction (v2)
# ═══════════════════════════════════════════════════════════════════════

def _get_governing_sentence_v2(text: str, match_start: int, match_end: int) -> str:
    """Return the full sentence containing the match, with improved boundary detection."""
    # Walk backward to sentence start (period, newline, or start-of-text)
    sent_start = match_start
    while sent_start > 0:
        ch = text[sent_start - 1]
        if ch == '.':
            break
        if ch == '\n' and sent_start < match_start - 1:
            break
        sent_start -= 1

    # Walk forward to sentence end
    sent_end = match_end
    while sent_end < len(text):
        if text[sent_end] == '.':
            sent_end += 1
            break
        sent_end += 1

    sentence = text[sent_start:sent_end].strip()
    sentence = re.sub(r'^[.;,\s\n]+', '', sentence).strip()
    return sentence


def _normalize_summary_v2(text: str, obligation_type: str) -> str:
    """Generate a concise normalized summary with type-aware truncation."""
    summary = text.strip()
    # Remove leading articles/connectors for cleaner summaries
    summary = re.sub(r'^(?:and |or |also |furthermore |moreover |in addition )', '', summary, flags=re.IGNORECASE)
    if len(summary) > 300:
        for sep in ['; ', ', ', ' — ', ' - ', ' and ']:
            idx = summary.find(sep, 100)
            if 100 < idx < 300:
                summary = summary[:idx]
                break
        else:
            summary = summary[:300].rsplit(' ', 1)[0] + '...'
    return summary


class ExtractedObligationV2:
    """An obligation extracted from text (v2 with improved fields)."""
    def __init__(self, text: str, obligation_type: str, confidence: float,
                 normalized_summary: str = None, condition: str = None,
                 deadline: str = None, applies_to: list = None,
                 extraction_method: str = "rule_based",
                 sub_type: str = None, severity_hint: str = None):
        self.text = text
        self.obligation_type = obligation_type
        self.confidence = confidence
        self.normalized_summary = normalized_summary or _normalize_summary_v2(text, obligation_type)
        self.condition = condition
        self.deadline = deadline
        self.applies_to = applies_to or []
        self.extraction_method = extraction_method
        self.sub_type = sub_type  # e.g., "cdd", "str_filing", "sanctions_screening"
        self.severity_hint = severity_hint  # e.g., "high", "medium", "low"


class ImprovedRuleBasedExtractor:
    """Improved rule-based obligation extraction (v2).

    Improvements over v1:
    - Better distinction: obligation, prohibition, penalty, guidance, definition
    - NEW: guidance and definition pattern detection
    - Reduced duplicates with stricter Jaccard threshold + positional overlap check
    - Improved applicability detection (product types + entity types)
    - Better Arabic/English extraction consistency (parallel patterns)
    - Sub-type classification for operational categorization
    """

    # ── Definition patterns (NEW) ─────────────────────────────────────
    DEFINITION_PATTERNS = [
        (r'(?:"[^"]+"|[\u2018\u2019][^\u2018\u2019]+[\u2018\u2019])\s+(?:means?|refers? to|is defined as|shall mean)\s+[^.]{10,300}\.', 'definition', 0.90),
        (r'\b(?:for the purposes? of|as used in)\s+(?:this|these)\b[^.]{10,200}\.', 'definition', 0.85),
        (r'\b(?:يُقصد بـ|يعني|يشير إلى|المقصود بـ)\b[^.。]{10,300}[.。]', 'definition', 0.85),
    ]

    # ── Guidance / recommendation patterns (NEW) ──────────────────────
    GUIDANCE_PATTERNS = [
        (r'\b(?:should|is encouraged|is recommended|are encouraged|are recommended|is expected)\b[^.]{10,200}\.', 'guidance', 0.70),
        (r'\b(?:best practice|good practice|recommended practice)\b[^.]{10,200}\.', 'guidance', 0.65),
        (r'\b(?:countries should|FIs should|institutions should|competent authorities should)\b[^.]{10,200}\.', 'guidance', 0.70),
        (r'\b(?:ينبغي|يُنصح|يُستحسن|من المستحسن|من الأفضل)\b[^.。]{10,200}[.。]', 'guidance', 0.70),
    ]

    # ── Penalty / enforcement (improved) ──────────────────────────────
    PENALTY_LANGUAGE_RE = re.compile(
        r'\b(?:sentenced?|convicted?|punished?|penalt(?:y|ies)|imprisonment|'
        r'fine[sd]?\s+(?:not|of|up)|confiscat(?:e|ed|ion)|years? in (?:prison|jail)|'
        r'criminal\s+(?:liability|prosecution|sanction)|'
        r'عقوبة|حبس|سجن|غرامة|مصادرة|يعاقب)\b',
        re.IGNORECASE,
    )

    PENALTY_PATTERNS = [
        (r'\b(?:sentenced?|convicted?|punished?|penalt(?:y|ies)|imprisonment|fine)\b[^.]{10,300}\.', 'penalty', 0.80),
        (r'\b(?:criminal\s+(?:liability|prosecution|sanction))\b[^.]{10,300}\.', 'penalty', 0.80),
        (r'\b(?:عقوبة|حبس|سجن|غرامة|مصادرة|يعاقب)\b[^.。]{10,300}[.。]', 'penalty', 0.75),
    ]

    # ── Mandatory / Prohibition (improved with sub-type detection) ────
    MANDATORY_PATTERNS = [
        (r'\b(?:shall|must|is required to|are required to|is obligated|are obligated)\b[^.]{10,200}\.', 'mandatory', 0.85),
        (r'\b(?:shall not|must not|is prohibited|are prohibited|may not|no person shall)\b[^.]{10,200}\.', 'prohibition', 0.85),
        (r'\b(?:يجب|يلتزم|يتعين|ملزم|على .{2,30} أن)\b[^.。]{10,200}[.。]', 'mandatory', 0.80),
        (r'\b(?:يحظر|لا يجوز|يمنع|ممنوع)\b[^.。]{10,200}[.。]', 'prohibition', 0.80),
    ]

    # ── Reporting / Deadline ──────────────────────────────────────────
    REPORTING_PATTERNS = [
        (r'\b(?:report|notify|inform|submit|file|disclose)\b[^.]{10,200}\.', 'reporting', 0.75),
        (r'\b(?:within \d+ (?:days?|hours?|months?|business days?))\b[^.]{5,200}\.', 'deadline', 0.80),
        (r'\b(?:إبلاغ|تقديم|إخطار|تقرير)\b[^.。]{10,200}[.。]', 'reporting', 0.75),
        (r'\b(?:خلال \d+ (?:أيام?|ساعات?|أشهر?))\b[^.。]{5,200}[.。]', 'deadline', 0.75),
    ]

    # ── Threshold triggers ────────────────────────────────────────────
    THRESHOLD_TRIGGER_PATTERNS = [
        r'\b(?:exceed|exceeding|above|more than|at least|minimum|maximum)\s+(?:SAR|USD|EUR|£|\$|ر\.س)?\s*[\d,]+',
        r'\b(?:تجاوز|يتجاوز|أكثر من|الحد الأدنى|الحد الأقصى)\s+[\d,]+',
    ]
    THRESHOLD_CONFIDENCE = 0.80

    # ── Governance ────────────────────────────────────────────────────
    GOVERNANCE_PATTERNS = [
        (r'\b(?:board|senior management|compliance officer|MLRO|designated officer)\b[^.]{10,200}(?:shall|must|responsible)[^.]{5,200}\.', 'governance', 0.75),
        (r'\b(?:مجلس الإدارة|الإدارة العليا|مسؤول الالتزام|المسؤول المعين)\b[^.。]{10,200}[.。]', 'governance', 0.70),
    ]

    # ── CDD / Identification / Verification ───────────────────────────
    CDD_PATTERNS = [
        (r'\b(?:identify|identifying)\s+(?:the\s+)?(?:customer|client|applicant|beneficial owner)[^.]{5,200}\.', 'identification', 0.85),
        (r'\b(?:verif(?:y|ying|ication))\s+(?:the\s+)?(?:customer|client|identity|identities|that customer)[^.]{5,200}\.', 'verification', 0.85),
        (r'\b(?:beneficial\s+owner(?:ship)?)\b[^.]{10,200}(?:identify|determine|verify|establish|reasonable measures)[^.]{5,200}\.', 'identification', 0.85),
        (r'\b(?:customer\s+due\s+diligence|CDD)\s+measures?\b[^.]{10,200}\.', 'mandatory', 0.85),
        (r'\b(?:ongoing\s+(?:due\s+diligence|monitoring|scrutiny))\b[^.]{10,200}\.', 'ongoing_monitoring', 0.80),
        (r'\b(?:maintain|keep|retain)\s+(?:all\s+)?(?:records?|documentation)\b[^.]{10,200}\.', 'recordkeeping', 0.80),
        (r'(?:should be|shall be|are|is)\s+required\s+to\s+(?:undertake|conduct|perform|carry out)\s+(?:customer\s+due\s+diligence|CDD)[^.]{5,200}\.', 'mandatory', 0.85),
        (r'\b(?:التعرف على|تحديد هوية|التحقق من هوية)\b[^.。]{10,200}[.。]', 'identification', 0.80),
        (r'\b(?:المستفيد الحقيقي|المالك المستفيد)\b[^.。]{10,200}[.。]', 'identification', 0.80),
    ]

    # ── Entity type patterns for applies_to ───────────────────────────
    ENTITY_PATTERNS = {
        "bank": r'\b(?:bank|banks|banking|مصرف|بنك|بنوك)\b',
        "fintech": r'\b(?:fintech|financial technology|تقنية مالية|فنتك)\b',
        "insurance": r'\b(?:insurance|insurer|reinsurance|تأمين|شركة تأمين)\b',
        "securities": r'\b(?:securities|broker|dealer|أوراق مالية|وسيط)\b',
        "exchange": r'\b(?:exchange house|money exchange|صرافة|محل صرافة)\b',
        "crowdfunding": r'\b(?:crowdfunding|crowd-funding|تمويل جماعي)\b',
        "payment": r'\b(?:payment service|e-wallet|digital wallet|خدمة دفع|محفظة إلكترونية)\b',
        "finance_company": r'\b(?:finance compan(?:y|ies)|شركة تمويل)\b',
        "dnfbp": r'\b(?:designated non-financial|DNFBPs?|المهن والأعمال غير المالية)\b',
        "all_financial": r'\b(?:financial institution|regulated entity|المنشأة المالية|الجهة الخاضعة|all FIs)\b',
    }

    # ── Product type patterns (NEW) ───────────────────────────────────
    PRODUCT_PATTERNS = {
        "wire_transfer": r'\b(?:wire transfer|fund transfer|حوالة|تحويل أموال)\b',
        "correspondent_banking": r'\b(?:correspondent banking|مراسلة بنكية)\b',
        "private_banking": r'\b(?:private banking|خدمات مصرفية خاصة)\b',
        "trade_finance": r'\b(?:trade finance|تمويل تجاري)\b',
        "digital_assets": r'\b(?:virtual asset|digital asset|crypto|أصول رقمية|أصول افتراضية)\b',
        "remittance": r'\b(?:remittance|money transfer|حوالات)\b',
        "loan": r'\b(?:loan|lending|credit|قرض|إقراض|تسهيلات ائتمانية)\b',
    }

    # ── Sub-type detection for operational categorization ──────────────
    SUB_TYPE_PATTERNS = {
        "cdd": r'\b(?:customer due diligence|CDD|KYC|know your customer|العناية الواجبة)\b',
        "str_filing": r'\b(?:suspicious transaction|STR|suspicious activity|الإبلاغ عن المعاملات المشتبه)\b',
        "sanctions_screening": r'\b(?:sanction(?:s|ed)?|designated (?:person|entity|list)|فحص العقوبات|القوائم)\b',
        "pep_screening": r'\b(?:politically exposed|PEP|أشخاص معرضون سياسياً)\b',
        "beneficial_ownership": r'\b(?:beneficial owner|UBO|المستفيد الحقيقي)\b',
        "record_keeping": r'\b(?:record(?:s|keeping)?|retention|حفظ السجلات)\b',
        "training": r'\b(?:training|awareness|employee education|تدريب)\b',
        "risk_assessment": r'\b(?:risk assessment|risk-based approach|تقييم المخاطر)\b',
        "transaction_monitoring": r'\b(?:transaction monitoring|unusual transaction|مراقبة المعاملات)\b',
        "internal_controls": r'\b(?:internal control|compliance program|برنامج الالتزام)\b',
    }

    MIN_OBLIGATION_LENGTH = 30
    MAX_OBLIGATION_LENGTH = 1000  # NEW: cap to avoid capturing full paragraphs

    @staticmethod
    def extract(text: str) -> list[ExtractedObligationV2]:
        """Extract obligations with improved classification and deduplication."""
        obligations: list[ExtractedObligationV2] = []
        seen_texts: set[str] = set()
        matched_spans: list[tuple[int, int, str]] = []  # (start, end, type)

        # --- Phase A: Definition detection (NEW) ---
        for pattern, ob_type, confidence in ImprovedRuleBasedExtractor.DEFINITION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                matched_text = match.group(0).strip()
                if len(matched_text) < ImprovedRuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue
                if len(matched_text) > ImprovedRuleBasedExtractor.MAX_OBLIGATION_LENGTH:
                    continue
                text_key = matched_text[:120].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)
                matched_spans.append((match.start(), match.end(), 'definition'))
                obligations.append(ExtractedObligationV2(
                    text=matched_text,
                    obligation_type='definition',
                    confidence=confidence,
                    applies_to=ImprovedRuleBasedExtractor._detect_entities(matched_text),
                    extraction_method="rule_based",
                ))

        # --- Phase B: Guidance detection (NEW) ---
        for pattern, ob_type, confidence in ImprovedRuleBasedExtractor.GUIDANCE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                matched_text = match.group(0).strip()
                if len(matched_text) < ImprovedRuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue
                if len(matched_text) > ImprovedRuleBasedExtractor.MAX_OBLIGATION_LENGTH:
                    continue
                # Skip if overlaps with definitions
                if ImprovedRuleBasedExtractor._overlaps_span(match.start(), match.end(), matched_spans):
                    continue
                text_key = matched_text[:120].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)

                # Check if this is actually a mandatory obligation disguised as guidance
                if re.search(r'\b(?:shall|must|required)\b', matched_text, re.IGNORECASE):
                    continue  # Let mandatory patterns catch it

                matched_spans.append((match.start(), match.end(), 'guidance'))
                applies_to = ImprovedRuleBasedExtractor._detect_entities(matched_text)
                obligations.append(ExtractedObligationV2(
                    text=matched_text,
                    obligation_type='guidance',
                    confidence=confidence,
                    applies_to=applies_to if applies_to else ["all_financial"],
                    extraction_method="rule_based",
                    severity_hint="low",
                ))

        # --- Phase C: Penalty detection ---
        penalty_spans: list[tuple[int, int]] = []
        for pattern, ob_type, confidence in ImprovedRuleBasedExtractor.PENALTY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                matched_text = match.group(0).strip()
                if len(matched_text) < ImprovedRuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue
                if len(matched_text) > ImprovedRuleBasedExtractor.MAX_OBLIGATION_LENGTH:
                    continue
                if ImprovedRuleBasedExtractor._overlaps_span(match.start(), match.end(), matched_spans):
                    continue
                text_key = matched_text[:120].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)
                penalty_spans.append((match.start(), match.end()))
                matched_spans.append((match.start(), match.end(), 'penalty'))
                applies_to = ImprovedRuleBasedExtractor._detect_entities(matched_text)
                obligations.append(ExtractedObligationV2(
                    text=matched_text,
                    obligation_type='penalty',
                    confidence=confidence,
                    condition=ImprovedRuleBasedExtractor._extract_condition(matched_text),
                    applies_to=applies_to if applies_to else ["all_financial"],
                    extraction_method="rule_based",
                    severity_hint="high",
                ))

        # --- Phase D: Standard patterns (mandatory, prohibition, reporting, governance, CDD) ---
        standard_patterns = (
            ImprovedRuleBasedExtractor.MANDATORY_PATTERNS +
            ImprovedRuleBasedExtractor.REPORTING_PATTERNS +
            ImprovedRuleBasedExtractor.GOVERNANCE_PATTERNS +
            ImprovedRuleBasedExtractor.CDD_PATTERNS
        )

        for pattern, ob_type, confidence in standard_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                matched_text = match.group(0).strip()
                if len(matched_text) < ImprovedRuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue
                if len(matched_text) > ImprovedRuleBasedExtractor.MAX_OBLIGATION_LENGTH:
                    continue

                # Skip if overlaps with already-classified spans
                if ImprovedRuleBasedExtractor._overlaps_span(match.start(), match.end(), matched_spans):
                    continue

                text_key = matched_text[:120].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)

                # Reclassify as penalty if penalty language present
                final_type = ob_type
                if ob_type in ('mandatory', 'prohibition') and ImprovedRuleBasedExtractor.PENALTY_LANGUAGE_RE.search(matched_text):
                    final_type = 'penalty'

                applies_to = ImprovedRuleBasedExtractor._detect_entities(matched_text)
                product_types = ImprovedRuleBasedExtractor._detect_products(matched_text)
                condition = ImprovedRuleBasedExtractor._extract_condition(matched_text)
                deadline = ImprovedRuleBasedExtractor._extract_deadline(matched_text)
                sub_type = ImprovedRuleBasedExtractor._detect_sub_type(matched_text)

                # Severity hint based on type
                severity_hint = "medium"
                if final_type in ('mandatory', 'prohibition'):
                    severity_hint = "high"
                elif final_type in ('reporting', 'deadline'):
                    severity_hint = "high"
                elif final_type in ('governance', 'recordkeeping'):
                    severity_hint = "medium"

                matched_spans.append((match.start(), match.end(), final_type))
                ob = ExtractedObligationV2(
                    text=matched_text,
                    obligation_type=final_type,
                    confidence=confidence,
                    condition=condition,
                    deadline=deadline,
                    applies_to=applies_to if applies_to else ["all_financial"],
                    extraction_method="rule_based",
                    sub_type=sub_type,
                    severity_hint=severity_hint,
                )
                ob.applies_to_products = product_types
                obligations.append(ob)

        # --- Phase E: Threshold extraction with full-sentence context ---
        for trigger_pattern in ImprovedRuleBasedExtractor.THRESHOLD_TRIGGER_PATTERNS:
            for match in re.finditer(trigger_pattern, text, re.IGNORECASE | re.MULTILINE):
                if ImprovedRuleBasedExtractor._overlaps_span(match.start(), match.end(), matched_spans):
                    continue
                governing = _get_governing_sentence_v2(text, match.start(), match.end())
                if len(governing) < ImprovedRuleBasedExtractor.MIN_OBLIGATION_LENGTH:
                    continue
                if len(governing) > ImprovedRuleBasedExtractor.MAX_OBLIGATION_LENGTH:
                    continue
                text_key = governing[:120].lower()
                if text_key in seen_texts:
                    continue
                seen_texts.add(text_key)

                matched_spans.append((match.start(), match.end(), 'threshold'))
                applies_to = ImprovedRuleBasedExtractor._detect_entities(governing)
                condition = ImprovedRuleBasedExtractor._extract_condition(governing)

                obligations.append(ExtractedObligationV2(
                    text=governing,
                    obligation_type='threshold',
                    confidence=ImprovedRuleBasedExtractor.THRESHOLD_CONFIDENCE,
                    condition=condition,
                    applies_to=applies_to if applies_to else ["all_financial"],
                    extraction_method="rule_based",
                    sub_type=ImprovedRuleBasedExtractor._detect_sub_type(governing),
                    severity_hint="medium",
                ))

        # --- Phase F: Improved deduplication ---
        obligations = ImprovedRuleBasedExtractor._deduplicate_v2(obligations)

        return obligations

    @staticmethod
    def _overlaps_span(start: int, end: int, spans: list[tuple[int, int, str]]) -> bool:
        """Check if a span overlaps with any existing classified spans (>50% overlap)."""
        for s_start, s_end, _ in spans:
            overlap_start = max(start, s_start)
            overlap_end = min(end, s_end)
            if overlap_end > overlap_start:
                overlap_len = overlap_end - overlap_start
                span_len = end - start
                if span_len > 0 and overlap_len / span_len > 0.5:
                    return True
        return False

    @staticmethod
    def _deduplicate_v2(
        obligations: list[ExtractedObligationV2],
    ) -> list[ExtractedObligationV2]:
        """Improved deduplication using Jaccard similarity + containment check."""
        TYPE_SPECIFICITY = {
            'definition': 12, 'penalty': 11, 'identification': 10, 'verification': 9,
            'ongoing_monitoring': 8, 'recordkeeping': 7, 'threshold': 6,
            'governance': 5, 'reporting': 4, 'deadline': 3,
            'prohibition': 2, 'mandatory': 1, 'guidance': 0,
        }
        if len(obligations) <= 1:
            return obligations

        # Build token sets
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
                jaccard = overlap / union

                # Containment check: if one is subset of the other
                smaller = min(len(token_sets[i]), len(token_sets[j]))
                containment = overlap / smaller if smaller > 0 else 0

                # Remove if Jaccard >= 0.80 OR containment >= 0.90
                if jaccard >= 0.80 or containment >= 0.90:
                    spec_i = TYPE_SPECIFICITY.get(obligations[i].obligation_type, 0)
                    spec_j = TYPE_SPECIFICITY.get(obligations[j].obligation_type, 0)
                    if spec_i >= spec_j:
                        to_remove.add(j)
                    else:
                        to_remove.add(i)
                        break

        return [ob for idx, ob in enumerate(obligations) if idx not in to_remove]

    @staticmethod
    def _detect_entities(text: str) -> list[str]:
        """Detect entity types mentioned in the text."""
        entities = []
        for entity_type, pattern in ImprovedRuleBasedExtractor.ENTITY_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                entities.append(entity_type)
        return entities

    @staticmethod
    def _detect_products(text: str) -> list[str]:
        """Detect product types mentioned in the text (NEW)."""
        products = []
        for product_type, pattern in ImprovedRuleBasedExtractor.PRODUCT_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                products.append(product_type)
        return products

    @staticmethod
    def _detect_sub_type(text: str) -> Optional[str]:
        """Detect operational sub-type for categorization (NEW)."""
        for sub_type, pattern in ImprovedRuleBasedExtractor.SUB_TYPE_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return sub_type
        return None

    @staticmethod
    def _extract_condition(text: str) -> Optional[str]:
        """Extract conditional clause from obligation text."""
        match = re.search(
            r'(?:if|when|where|in case|provided that|unless|except when)\s+([^,\.]{5,150})',
            text, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        match_ar = re.search(r'(?:إذا|عندما|في حال|بشرط|ما لم)\s+([^,\.。]{5,150})', text)
        if match_ar:
            return match_ar.group(1).strip()
        return None

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
            r'(?:minimum of|at least|no later than)\s+(\d+\s+(?:years?|months?|days?))',
            text, re.IGNORECASE
        )
        if match2:
            return match2.group(1)
        return None


class ImprovedExtractionService:
    """Manages improved obligation extraction from regulatory provisions."""

    @staticmethod
    async def extract_from_provision_v2(
        db: AsyncSession,
        provision_id: str,
    ) -> list[Obligation]:
        """Extract obligations using improved v2 extractor."""
        provision = await db.get(Provision, provision_id)
        if not provision:
            return []

        extracted = ImprovedRuleBasedExtractor.extract(provision.text)

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
                applies_to_product_types=getattr(ext, 'applies_to_products', None),
                condition=ext.condition,
                deadline=ext.deadline,
                confidence=ext.confidence,
                extraction_method=ExtractionMethod.RULE_BASED,
                review_status=ReviewStatus.PENDING,
                criticality=ext.severity_hint,
            )
            db.add(ob)
            obligations.append(ob)

        await db.flush()
        return obligations

    @staticmethod
    async def extract_all_v2(
        db: AsyncSession,
        force: bool = False,
    ) -> dict:
        """Extract obligations from ALL provisions using improved v2 logic.

        Returns stats on extraction.
        """
        from sqlalchemy import delete as sql_delete
        from app.models.regulatory.change import ReviewDecision

        deleted_count = 0
        if force:
            await db.execute(sql_delete(ReviewDecision))
            # Also clean obligation-control mappings
            await db.execute(sql_delete(ObligationControl))
            result = await db.execute(sql_delete(Obligation))
            deleted_count = result.rowcount
            await db.flush()

        prov_result = await db.execute(select(Provision.id))
        all_prov_ids = [row[0] for row in prov_result.all()]

        existing_result = await db.execute(select(Obligation.provision_id).distinct())
        existing_prov_ids = {row[0] for row in existing_result.all()}

        new_prov_ids = [pid for pid in all_prov_ids if pid not in existing_prov_ids]

        total_extracted = 0
        by_type = defaultdict(int)
        for prov_id in new_prov_ids:
            obligations = await ImprovedExtractionService.extract_from_provision_v2(db, prov_id)
            total_extracted += len(obligations)
            for ob in obligations:
                ob_type = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
                by_type[ob_type] += 1

        return {
            "total_provisions": len(all_prov_ids),
            "provisions_processed": len(new_prov_ids),
            "provisions_skipped": len(existing_prov_ids),
            "obligations_extracted": total_extracted,
            "deleted_pre_existing": deleted_count,
            "by_type": dict(by_type),
            "extractor_version": "v2_improved",
        }

    @staticmethod
    async def get_extraction_comparison(db: AsyncSession, provision_id: str) -> dict:
        """Compare v1 vs v2 extraction on a single provision (for before/after evidence)."""
        from app.services.regulatory.obligation_extraction_service import RuleBasedExtractor

        provision = await db.get(Provision, provision_id)
        if not provision:
            return {"error": "Provision not found"}

        v1_results = RuleBasedExtractor.extract(provision.text)
        v2_results = ImprovedRuleBasedExtractor.extract(provision.text)

        v1_types = defaultdict(int)
        for ob in v1_results:
            v1_types[ob.obligation_type] += 1

        v2_types = defaultdict(int)
        for ob in v2_results:
            v2_types[ob.obligation_type] += 1

        return {
            "provision_id": provision_id,
            "provision_title": provision.title,
            "text_length": len(provision.text),
            "v1": {
                "total": len(v1_results),
                "by_type": dict(v1_types),
                "obligations": [
                    {"text": ob.text[:200], "type": ob.obligation_type, "confidence": ob.confidence}
                    for ob in v1_results
                ],
            },
            "v2": {
                "total": len(v2_results),
                "by_type": dict(v2_types),
                "obligations": [
                    {
                        "text": ob.text[:200],
                        "type": ob.obligation_type,
                        "confidence": ob.confidence,
                        "sub_type": ob.sub_type,
                        "severity_hint": ob.severity_hint,
                        "applies_to": ob.applies_to,
                    }
                    for ob in v2_results
                ],
            },
            "improvements": {
                "new_types_detected": [t for t in v2_types if t not in v1_types],
                "count_change": len(v2_results) - len(v1_results),
                "new_classifications": ["guidance", "definition"] if any(t in v2_types for t in ["guidance", "definition"]) else [],
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. Automated Control Suggestions
# ═══════════════════════════════════════════════════════════════════════

# Control suggestion templates keyed by obligation sub-type or type
_CONTROL_TEMPLATES = {
    "cdd": {
        "name": "Customer Due Diligence Procedure",
        "name_ar": "إجراء العناية الواجبة للعميل",
        "objective": "Ensure proper identification and verification of customers before establishing business relationships",
        "objective_ar": "ضمان التعرف والتحقق من العملاء قبل إقامة علاقات العمل",
        "control_type": "procedure",
        "suggested_owner": "Compliance Department",
        "suggested_frequency": "per_transaction",
    },
    "str_filing": {
        "name": "Suspicious Transaction Reporting Procedure",
        "name_ar": "إجراء الإبلاغ عن المعاملات المشتبه بها",
        "objective": "Ensure timely identification and reporting of suspicious transactions to SAFIU",
        "objective_ar": "ضمان التحديد والإبلاغ في الوقت المناسب عن المعاملات المشتبه بها إلى وحدة التحريات المالية",
        "control_type": "procedure",
        "suggested_owner": "MLRO",
        "suggested_frequency": "continuous",
    },
    "sanctions_screening": {
        "name": "Sanctions Screening System",
        "name_ar": "نظام فحص العقوبات",
        "objective": "Screen all customers and transactions against sanctions lists",
        "objective_ar": "فحص جميع العملاء والمعاملات مقابل قوائم العقوبات",
        "control_type": "technical",
        "suggested_owner": "Compliance Technology",
        "suggested_frequency": "continuous",
    },
    "pep_screening": {
        "name": "PEP Screening & Enhanced Due Diligence",
        "name_ar": "فحص الأشخاص المعرضين سياسياً والعناية الواجبة المعززة",
        "objective": "Identify PEPs and apply enhanced due diligence measures",
        "objective_ar": "تحديد الأشخاص المعرضين سياسياً وتطبيق إجراءات العناية الواجبة المعززة",
        "control_type": "procedure",
        "suggested_owner": "Compliance Department",
        "suggested_frequency": "per_transaction",
    },
    "beneficial_ownership": {
        "name": "Beneficial Ownership Verification",
        "name_ar": "التحقق من المستفيد الحقيقي",
        "objective": "Identify and verify beneficial owners of legal entities",
        "objective_ar": "تحديد والتحقق من المستفيدين الحقيقيين للكيانات القانونية",
        "control_type": "procedure",
        "suggested_owner": "Compliance Department",
        "suggested_frequency": "per_transaction",
    },
    "record_keeping": {
        "name": "Record Keeping & Retention Policy",
        "name_ar": "سياسة حفظ السجلات والاحتفاظ بها",
        "objective": "Maintain all required records for the minimum retention period",
        "objective_ar": "الاحتفاظ بجميع السجلات المطلوبة لفترة الاحتفاظ الدنيا",
        "control_type": "policy",
        "suggested_owner": "Records Management",
        "suggested_frequency": "quarterly",
    },
    "training": {
        "name": "AML/CTF Training Program",
        "name_ar": "برنامج التدريب على مكافحة غسل الأموال وتمويل الإرهاب",
        "objective": "Ensure all relevant staff receive AML/CTF training",
        "objective_ar": "ضمان حصول جميع الموظفين المعنيين على التدريب",
        "control_type": "training",
        "suggested_owner": "HR / Compliance",
        "suggested_frequency": "annual",
    },
    "risk_assessment": {
        "name": "AML/CTF Risk Assessment",
        "name_ar": "تقييم مخاطر غسل الأموال وتمويل الإرهاب",
        "objective": "Conduct periodic risk assessments of ML/TF risks",
        "objective_ar": "إجراء تقييمات دورية لمخاطر غسل الأموال وتمويل الإرهاب",
        "control_type": "procedure",
        "suggested_owner": "Risk Management",
        "suggested_frequency": "annual",
    },
    "transaction_monitoring": {
        "name": "Transaction Monitoring System",
        "name_ar": "نظام مراقبة المعاملات",
        "objective": "Monitor transactions for unusual or suspicious patterns",
        "objective_ar": "مراقبة المعاملات للكشف عن أنماط غير عادية أو مشبوهة",
        "control_type": "technical",
        "suggested_owner": "Compliance Technology",
        "suggested_frequency": "continuous",
    },
    "internal_controls": {
        "name": "AML/CTF Internal Controls Framework",
        "name_ar": "إطار الضوابط الداخلية لمكافحة غسل الأموال",
        "objective": "Maintain an effective internal controls framework for AML/CTF compliance",
        "objective_ar": "الحفاظ على إطار فعال للضوابط الداخلية للالتزام بمكافحة غسل الأموال",
        "control_type": "policy",
        "suggested_owner": "Compliance Department",
        "suggested_frequency": "quarterly",
    },
}

# Fallback templates by obligation type when no sub-type matches
_TYPE_FALLBACK_TEMPLATES = {
    "mandatory": {
        "name": "Regulatory Compliance Control",
        "name_ar": "ضابط الامتثال التنظيمي",
        "objective": "Ensure compliance with mandatory regulatory requirement",
        "objective_ar": "ضمان الامتثال للمتطلبات التنظيمية الإلزامية",
        "control_type": "procedure",
        "suggested_owner": "Compliance Department",
        "suggested_frequency": "monthly",
    },
    "prohibition": {
        "name": "Prohibited Activity Prevention Control",
        "name_ar": "ضابط منع الأنشطة المحظورة",
        "objective": "Prevent prohibited activities through policies and monitoring",
        "objective_ar": "منع الأنشطة المحظورة من خلال السياسات والمراقبة",
        "control_type": "monitoring",
        "suggested_owner": "Compliance Department",
        "suggested_frequency": "continuous",
    },
    "reporting": {
        "name": "Regulatory Reporting Procedure",
        "name_ar": "إجراء التقارير التنظيمية",
        "objective": "Ensure timely and accurate regulatory reporting",
        "objective_ar": "ضمان تقديم التقارير التنظيمية في الوقت المناسب وبدقة",
        "control_type": "procedure",
        "suggested_owner": "MLRO",
        "suggested_frequency": "monthly",
    },
    "governance": {
        "name": "Governance & Oversight Control",
        "name_ar": "ضابط الحوكمة والإشراف",
        "objective": "Ensure proper governance and oversight of AML/CTF program",
        "objective_ar": "ضمان الحوكمة والإشراف المناسبين على برنامج مكافحة غسل الأموال",
        "control_type": "policy",
        "suggested_owner": "Board / Senior Management",
        "suggested_frequency": "quarterly",
    },
    "threshold": {
        "name": "Threshold Monitoring & Reporting",
        "name_ar": "مراقبة الحدود والإبلاغ",
        "objective": "Monitor and report transactions exceeding regulatory thresholds",
        "objective_ar": "مراقبة المعاملات التي تتجاوز الحدود التنظيمية والإبلاغ عنها",
        "control_type": "technical",
        "suggested_owner": "Compliance Technology",
        "suggested_frequency": "continuous",
    },
}


class ControlSuggestionService:
    """Generate suggested controls from obligation text.

    Each suggestion includes: name, objective, type, owner, frequency, rationale, confidence.
    All suggestions are clearly marked as suggestions requiring human review.
    """

    @staticmethod
    async def suggest_controls_for_obligation(
        db: AsyncSession,
        obligation_id: str,
    ) -> Optional[dict]:
        """Generate control suggestions for a single obligation."""
        ob = await db.get(Obligation, obligation_id)
        if not ob:
            return None

        ob_type = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)

        # Detect sub-type from obligation text
        sub_type = None
        for st, pattern in ImprovedRuleBasedExtractor.SUB_TYPE_PATTERNS.items():
            if re.search(pattern, ob.text, re.IGNORECASE):
                sub_type = st
                break

        # Get template
        template = _CONTROL_TEMPLATES.get(sub_type) if sub_type else None
        if not template:
            template = _TYPE_FALLBACK_TEMPLATES.get(ob_type, _TYPE_FALLBACK_TEMPLATES["mandatory"])

        # Calculate confidence based on match quality
        confidence = 0.70
        if sub_type:
            confidence = 0.85  # Higher confidence when sub-type matches a known template
        if ob_type in ('mandatory', 'prohibition'):
            confidence = min(confidence + 0.05, 0.95)

        # Build rationale
        rationale = f"This control addresses the {ob_type} obligation"
        if sub_type:
            rationale += f" related to {sub_type.replace('_', ' ')}"
        rationale += f". Obligation text: \"{ob.text[:150]}...\""

        rationale_ar = f"يعالج هذا الضابط التزام {ob_type}"
        if sub_type:
            rationale_ar += f" المتعلق بـ {sub_type.replace('_', ' ')}"

        # Get provenance info
        provision = await db.get(Provision, ob.provision_id)
        provenance = {"provision_id": ob.provision_id}
        if provision:
            provenance["provision_section"] = provision.section_number
            provenance["provision_title"] = provision.title
            doc = await db.get(RegulatoryDocument, provision.document_id)
            if doc:
                reg = await db.get(Regulator, doc.regulator_id)
                provenance["source_title"] = doc.title
                provenance["regulator"] = reg.abbreviation if reg else None

        # Check if obligation already has controls mapped
        existing_count = (await db.execute(
            select(func.count(ObligationControl.control_id)).where(
                ObligationControl.obligation_id == obligation_id
            )
        )).scalar() or 0

        suggestion = {
            "obligation_id": obligation_id,
            "obligation_type": ob_type,
            "obligation_text": ob.text[:300],
            "sub_type": sub_type,
            "is_suggestion": True,  # Clearly marked as suggestion
            "status": "pending_review",  # Requires human acceptance
            "existing_controls_count": existing_count,
            "suggested_control": {
                "name": template["name"],
                "name_ar": template["name_ar"],
                "objective": template["objective"],
                "objective_ar": template["objective_ar"],
                "control_type": template["control_type"],
                "suggested_owner": template["suggested_owner"],
                "suggested_frequency": template["suggested_frequency"],
                "rationale": rationale,
                "rationale_ar": rationale_ar,
                "confidence": round(confidence, 2),
            },
            "provenance": provenance,
        }

        return suggestion

    @staticmethod
    async def suggest_controls_for_all(
        db: AsyncSession,
        only_unmapped: bool = True,
        min_confidence: float = 0.0,
    ) -> list[dict]:
        """Generate control suggestions for all (or unmapped) obligations."""
        query = select(Obligation).where(Obligation.is_active == True)

        if only_unmapped:
            # Only obligations without any mapped controls
            mapped_ids = select(ObligationControl.obligation_id).distinct()
            query = query.where(~Obligation.id.in_(mapped_ids))

        result = await db.execute(query.order_by(Obligation.created_at.desc()))
        obligations = list(result.scalars().all())

        suggestions = []
        for ob in obligations:
            suggestion = await ControlSuggestionService.suggest_controls_for_obligation(db, ob.id)
            if suggestion and suggestion["suggested_control"]["confidence"] >= min_confidence:
                suggestions.append(suggestion)

        return suggestions

    @staticmethod
    async def accept_suggestion(
        db: AsyncSession,
        obligation_id: str,
        control_name: str = None,
        control_name_ar: str = None,
        control_type: str = None,
        description: str = None,
        description_ar: str = None,
        owner: str = None,
        frequency: str = None,
    ) -> Optional[dict]:
        """Accept a control suggestion — create a real control and map it to the obligation.

        The caller can override any suggested field before accepting.
        """
        ob = await db.get(Obligation, obligation_id)
        if not ob:
            return None

        # Generate suggestion first to get defaults
        suggestion = await ControlSuggestionService.suggest_controls_for_obligation(db, obligation_id)
        if not suggestion:
            return None

        defaults = suggestion["suggested_control"]

        # Create the control with overrides or defaults
        control = Control(
            id=generate_uuid(),
            name=control_name or defaults["name"],
            name_ar=control_name_ar or defaults["name_ar"],
            description=description or defaults["objective"],
            description_ar=description_ar or defaults["objective_ar"],
            control_type=ControlType(control_type or defaults["control_type"]),
            owner=owner or defaults["suggested_owner"],
            frequency=frequency or defaults["suggested_frequency"],
            status=ControlStatus.DRAFT,
        )
        db.add(control)
        await db.flush()

        # Map to obligation
        mapping = ObligationControl(
            obligation_id=obligation_id,
            control_id=control.id,
            mapping_confidence=defaults["confidence"],
            mapping_method="ai_suggested",
            notes=f"Auto-suggested control accepted by human reviewer. Sub-type: {suggestion.get('sub_type', 'general')}",
        )
        db.add(mapping)
        await db.flush()

        return {
            "control_id": control.id,
            "control_name": control.name,
            "obligation_id": obligation_id,
            "mapping_method": "ai_suggested",
            "confidence": defaults["confidence"],
            "status": "accepted",
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. Evidence Expiry Alerts
# ═══════════════════════════════════════════════════════════════════════

class EvidenceExpiryAlertService:
    """Surface expired and soon-to-expire evidence artifacts."""

    @staticmethod
    async def get_expiry_alerts(
        db: AsyncSession,
        days_ahead: int = 30,
        include_expired: bool = True,
    ) -> dict:
        """Get evidence expiry alerts.

        Returns:
        - expired: evidence that has already expired
        - expiring_soon: evidence expiring within days_ahead
        - summary: counts and stats
        """
        now = datetime.now(timezone.utc)
        soon = now + timedelta(days=days_ahead)

        alerts = {"expired": [], "expiring_soon": [], "summary": {}}

        # Get all evidence with expiry dates
        all_evidence_q = select(EvidenceArtifact).where(
            EvidenceArtifact.expires_at.isnot(None)
        )
        result = await db.execute(all_evidence_q)
        all_with_expiry = list(result.scalars().all())

        total_with_expiry = len(all_with_expiry)
        expired_count = 0
        expiring_soon_count = 0

        for ev in all_with_expiry:
            expires_at = ev.expires_at
            if not expires_at:
                continue

            # Make timezone-aware if naive
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            # Get control info
            control = await db.get(Control, ev.control_id)
            control_name = control.name if control else "Unknown"
            control_name_ar = control.name_ar if control else None

            # Get obligation chain for this control
            ob_count = 0
            regulator = None
            if control:
                oc_count = (await db.execute(
                    select(func.count(ObligationControl.obligation_id)).where(
                        ObligationControl.control_id == control.id
                    )
                )).scalar() or 0
                ob_count = oc_count

            alert_item = {
                "evidence_id": ev.id,
                "evidence_name": ev.name,
                "evidence_name_ar": ev.name_ar,
                "artifact_type": ev.artifact_type,
                "owner": ev.owner,
                "control_id": ev.control_id,
                "control_name": control_name,
                "control_name_ar": control_name_ar,
                "obligations_affected": ob_count,
                "expires_at": str(ev.expires_at),
                "status": ev.status,
                "periodicity": ev.periodicity,
            }

            if expires_at <= now:
                # Already expired
                days_overdue = (now - expires_at).days
                alert_item["days_overdue"] = days_overdue
                alert_item["severity"] = "critical" if days_overdue > 30 else "high"
                alert_item["alert_type"] = "expired"
                alerts["expired"].append(alert_item)
                expired_count += 1
            elif expires_at <= soon:
                # Expiring soon
                days_until = (expires_at - now).days
                alert_item["days_until_expiry"] = days_until
                alert_item["severity"] = "high" if days_until <= 7 else "medium"
                alert_item["alert_type"] = "expiring_soon"
                alerts["expiring_soon"].append(alert_item)
                expiring_soon_count += 1

        # Sort by urgency
        alerts["expired"].sort(key=lambda x: x.get("days_overdue", 0), reverse=True)
        alerts["expiring_soon"].sort(key=lambda x: x.get("days_until_expiry", 999))

        # Total evidence count
        total_evidence = (await db.execute(
            select(func.count(EvidenceArtifact.id))
        )).scalar() or 0

        # Evidence without expiry date
        no_expiry = total_evidence - total_with_expiry

        alerts["summary"] = {
            "total_evidence": total_evidence,
            "total_with_expiry": total_with_expiry,
            "total_without_expiry": no_expiry,
            "expired_count": expired_count,
            "expiring_soon_count": expiring_soon_count,
            "healthy_count": total_with_expiry - expired_count - expiring_soon_count,
            "days_ahead_window": days_ahead,
            "checked_at": now.isoformat(),
        }

        return alerts

    @staticmethod
    async def update_evidence_expiry(
        db: AsyncSession,
        evidence_id: str,
        new_expires_at: datetime,
    ) -> Optional[dict]:
        """Update the expiry date of an evidence artifact (e.g., after renewal)."""
        ev = await db.get(EvidenceArtifact, evidence_id)
        if not ev:
            return None

        old_expires = str(ev.expires_at) if ev.expires_at else None
        ev.expires_at = new_expires_at

        # If it was expired, set status back to active
        now = datetime.now(timezone.utc)
        if new_expires_at.tzinfo is None:
            new_expires_at = new_expires_at.replace(tzinfo=timezone.utc)
        if new_expires_at > now and ev.status == "expired":
            ev.status = "active"

        await db.flush()

        return {
            "evidence_id": ev.id,
            "name": ev.name,
            "old_expires_at": old_expires,
            "new_expires_at": str(ev.expires_at),
            "status": ev.status,
        }

    @staticmethod
    async def auto_mark_expired(db: AsyncSession) -> dict:
        """Automatically mark expired evidence as 'expired' status."""
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(EvidenceArtifact).where(
                EvidenceArtifact.expires_at.isnot(None),
                EvidenceArtifact.status == "active",
            )
        )
        evidence_items = list(result.scalars().all())

        marked_count = 0
        for ev in evidence_items:
            expires_at = ev.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at <= now:
                ev.status = "expired"
                marked_count += 1

        await db.flush()

        return {
            "checked": len(evidence_items),
            "newly_marked_expired": marked_count,
            "checked_at": now.isoformat(),
        }
