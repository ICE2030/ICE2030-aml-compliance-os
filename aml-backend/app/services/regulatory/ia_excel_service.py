"""Insurance Authority (IA) Excel Ingestion, Classification & Reconciliation Service.

This module handles the full lifecycle of IA regulation data:

1. **Parsing**: Reads the official IA Excel file (27 sheets, varying column layouts)
   and normalises rows into a uniform internal structure.

2. **Classification**: Each row is classified as one of:
   - HEADING       – structural heading / part / chapter title (no obligation)
   - DEFINITION    – defines a term (provision only, no obligation)
   - OBLIGATION    – binding "shall / must" requirement → creates Obligation
   - PROHIBITION   – binding "shall not / may not" prohibition → creates Obligation
   - PENALTY       – penalty / sanction clause → creates Obligation(type=penalty)
   - REPORTING     – reporting / filing requirement → creates Obligation
   - GUIDANCE      – non-binding "should / recommended" → creates Obligation(type=guidance)
   - DESCRIPTIVE   – explanatory / contextual text (provision only, no obligation)
   - METADATA      – empty or administrative (skipped entirely)

3. **Seeding**: Creates Source → RegulatoryDocument → Provision → Obligation chain,
   preserving hierarchy (article > para > item > point), bilingual content, and
   provenance (IA regulator, SA jurisdiction, pack_id, seed_key).

4. **Reconciliation**: Compares spreadsheet content against existing DB records
   and reports new / changed / missing / duplicate provisions without silent overwrites.

5. **Sync Workflow**: Idempotent import that can be safely re-run.
   Uses content hashes to detect changes.  Existing records are never silently
   overwritten — changes are reported for human review.

Column layout patterns across sheets (header-based detection):
  Standard (most sheets): Article | ArticleText | Para | ParaText | Item | ItemText | Point | PointText | Applied | AR...
  Investment:             Parts | PartText | Section | SectionText | Article | ArticleText | Para | ParaText | Point | PointText | Applied | AR...
  Brokers/Agents:         Part | PartText | ... | Article | ArticleText | Item | ItemText | Point | PointText | Applied | AR...
  Risk Management:        Article | ArticleText | None | Para | ParaText | Item | ItemText | Point | PointText | Applied | AR...
  Actuarial:              Section | SectionText | Article | ArticleText | Item | ItemText | Point | PointText | Applied | AR...
  Implementing Regs:      Contents | Article | ArticleText | Para | ParaText | Item | ItemText | Point | PointText | ... | Applied | AR...
  AML&CTF:                Standard EN header but data only in AR columns
"""
import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import openpyxl
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.source import (
    Regulator, Jurisdiction, RegulatoryDocument, Provision, ProvisionType,
    Source, SourceVersion, DocumentStatus,
)
from app.models.base import generate_uuid
from app.models.regulatory.obligation import (
    Obligation, ObligationType, ExtractionMethod, ReviewStatus,
)
from regulator_packs.insurance_authority import IA_DOCUMENTS

logger = logging.getLogger(__name__)

_DEFAULT_EXCEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "regulator_packs" / "insurance_authority" / "data" / "ia_regulations.xlsx"
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Row Classification
# ═══════════════════════════════════════════════════════════════════════════════

class RowClass(str, Enum):
    """Classification of a spreadsheet row."""
    HEADING = "heading"
    DEFINITION = "definition"
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PENALTY = "penalty"
    REPORTING = "reporting"
    GUIDANCE = "guidance"
    DESCRIPTIVE = "descriptive"
    METADATA = "metadata"


# Maps RowClass → whether an Obligation record should be created
_CREATES_OBLIGATION = {
    RowClass.OBLIGATION: True,
    RowClass.PROHIBITION: True,
    RowClass.PENALTY: True,
    RowClass.REPORTING: True,
    RowClass.GUIDANCE: True,
    RowClass.HEADING: False,
    RowClass.DEFINITION: False,
    RowClass.DESCRIPTIVE: False,
    RowClass.METADATA: False,
}

# Maps RowClass → ObligationType
_ROW_TO_OBLIGATION_TYPE = {
    RowClass.OBLIGATION: ObligationType.MANDATORY,
    RowClass.PROHIBITION: ObligationType.PROHIBITION,
    RowClass.PENALTY: ObligationType.PENALTY,
    RowClass.REPORTING: ObligationType.REPORTING,
    RowClass.GUIDANCE: ObligationType.GUIDANCE,
}

# Maps RowClass → ProvisionType
_ROW_TO_PROVISION_TYPE = {
    RowClass.HEADING: ProvisionType.CHAPTER,
    RowClass.DEFINITION: ProvisionType.DEFINITION,
}


def _classify_text(text_en: str, text_ar: str) -> RowClass:
    """Classify a provision row based on its text content.

    Uses pattern matching on both EN and AR text to determine the semantic
    role of the row.  Order of checks matters — more specific patterns
    (definition, penalty, prohibition) are checked BEFORE the short-text
    heading heuristic to avoid misclassifying short but meaningful rows.
    """
    combined = f"{text_en} {text_ar}".strip()
    if not combined or len(combined) < 3:
        return RowClass.METADATA

    en_lower = text_en.lower().strip() if text_en else ""
    ar_text = text_ar.strip() if text_ar else ""

    # ── HEADING (explicit patterns only) ─────────────────────────────
    # Only match well-known structural headings by explicit pattern.
    heading_patterns_en = [
        r'^part\s+\d',
        r'^chapter\s+\d',
        r'^section\s+\d',
        r'^annex\b',
        r'^schedule\b',
        r'^appendix\b',
        r'^introduction$',
        r'^scope\s+and\s+exemptions?$',
        r'^compliance\s+measures$',
        r'^purpose$',
        r'^definitions?$',
        r'^general\s+(provisions?|requirements?)$',
        r'^enforcement$',
        r'^transitional\s+provisions?$',
        r'^final\s+provisions?$',
    ]
    heading_patterns_ar = [
        r'^الجزء\s',
        r'^الباب\s',
        r'^الفصل\s',
        r'^المادة\s+\d',
        r'^مقدمة$',
        r'^تعريفات$',
        r'^أحكام\s+(عامة|ختامية|انتقالية)',
        r'^نطاق\s+التطبيق',
    ]

    for pat in heading_patterns_en:
        if re.match(pat, en_lower, re.IGNORECASE):
            return RowClass.HEADING
    for pat in heading_patterns_ar:
        if re.match(pat, ar_text):
            return RowClass.HEADING

    # ── DEFINITION: "means", "refers to", "defined as" ──────────────
    # Check definitions BEFORE the short-text heading heuristic
    definition_patterns = [
        r'\b(?:means?|refers?\s+to|is\s+defined\s+as|shall\s+mean)\b',
        r'(?:يُقصد\s+بـ|يعني|يشير\s+إلى|المقصود\s+بـ|يُعرّف)',
        r'^"[^"]+"\s+(?:means|refers)',
        r'^مفهوم\s+',
    ]
    for pat in definition_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return RowClass.DEFINITION

    # ── PENALTY: penalty/sanction/imprisonment/fine ──────────────────
    # Check penalties BEFORE the short-text heading heuristic
    penalty_patterns = [
        r'\b(?:penalt(?:y|ies)|fine[sd]?\s+(?:not|of|up)|imprisonment|sentenced?|punished?|convicted?)',
        r'\b(?:criminal\s+(?:liability|prosecution|sanction))',
        r'\b(?:confiscat(?:e|ed|ion))',
        r'\b(?:years?\s+in\s+(?:prison|jail))',
        r'(?:عقوبة|حبس|سجن|غرامة|مصادرة|يعاقب|يُعاقب)',
        r'\b(?:non-compliance|breach)\b.{0,60}\b(?:deemed|subject\s+to)\b',
    ]
    for pat in penalty_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return RowClass.PENALTY

    # ── Short-text heading heuristic ─────────────────────────────────
    # Only AFTER checking definitions/penalties: short text with no verb
    # patterns is likely a heading.
    if len(combined) < 50 and not re.search(r'\b(shall|must|should|may|يجب|يلتزم|يحظر|لا يجوز|ينبغي)\b', combined, re.IGNORECASE):
        return RowClass.HEADING

    # ── PROHIBITION: "shall not", "must not", "prohibited", "may not"
    prohibition_patterns = [
        r'\b(?:shall\s+not|must\s+not|is\s+prohibited|are\s+prohibited|may\s+not|no\s+person\s+shall)',
        r'(?:يحظر|لا\s+يجوز|يمنع|ممنوع|لا\s+يحق)',
    ]
    for pat in prohibition_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return RowClass.PROHIBITION

    # ── REPORTING: report/notify/submit reports/file/disclose ─────────
    # "submit" alone is too broad (e.g. "submit an application" isn't reporting).
    # Require "submit" to be followed by a reporting-context word.
    reporting_patterns = [
        r'\b(?:shall|must|required\s+to)\b.{0,40}\b(?:report|notify|inform|disclose)\b',
        r'\b(?:shall|must|required\s+to)\b.{0,40}\bsubmit\b.{0,30}\b(?:report|return|filing|disclosure|notification|statement)\b',
        r'\bsubmit\b.{0,20}\b(?:quarterly|annual|monthly|periodic)\b.{0,20}\breport',
        r'\b(?:within\s+\d+\s+(?:days?|hours?|months?|business\s+days?))\b',
        r'(?:إبلاغ|تقديم\s+تقرير|إخطار).{0,40}(?:يجب|يلتزم)',
        r'(?:خلال\s+\d+\s+(?:أيام?|ساعات?|أشهر?))',
    ]
    for pat in reporting_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return RowClass.REPORTING

    # ── OBLIGATION: "shall", "must", "required to", "obligated" ─────
    obligation_patterns = [
        r'\b(?:shall|must|is\s+required\s+to|are\s+required\s+to|is\s+obligated|are\s+obligated)\b',
        r'(?:يجب|يلتزم|يتعين|ملزم|على\s+.{2,30}\s+أن)',
    ]
    for pat in obligation_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return RowClass.OBLIGATION

    # ── GUIDANCE: "should", "encouraged", "recommended" ──────────────
    guidance_patterns = [
        r'\b(?:should|is\s+encouraged|is\s+recommended|are\s+encouraged|best\s+practice)\b',
        r'(?:ينبغي|يُنصح|يُستحسن|من\s+المستحسن|من\s+الأفضل)',
    ]
    for pat in guidance_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return RowClass.GUIDANCE

    # ── DESCRIPTIVE: everything else with meaningful text ────────────
    if len(combined) > 10:
        return RowClass.DESCRIPTIVE

    return RowClass.METADATA


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Excel Parsing (header-adaptive)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ParsedRow:
    """A single normalised row from an IA Excel sheet."""
    sheet_name: str
    row_number: int

    # Hierarchy numbers (may be numeric or alphanumeric e.g. "a", "b")
    article_num: Optional[str] = None
    para_num: Optional[str] = None
    item_num: Optional[str] = None
    point_ref: Optional[str] = None

    # English text at each hierarchy level
    article_text_en: str = ""
    para_text_en: str = ""
    item_text_en: str = ""
    point_text_en: str = ""

    # Arabic text at each hierarchy level
    article_text_ar: str = ""
    para_text_ar: str = ""
    item_text_ar: str = ""
    point_text_ar: str = ""

    # Applied status
    applied: Optional[str] = None

    # Extra hierarchy levels (some sheets have Part/Section/Chapter/Contents)
    extra_level_en: str = ""
    extra_level_ar: str = ""

    # Computed fields
    row_class: RowClass = RowClass.METADATA
    content_hash: str = ""

    @property
    def best_text_en(self) -> str:
        """Most granular non-empty English text."""
        return (self.point_text_en or self.item_text_en or
                self.para_text_en or self.article_text_en or
                self.extra_level_en or "").strip()

    @property
    def best_text_ar(self) -> str:
        """Most granular non-empty Arabic text."""
        return (self.point_text_ar or self.item_text_ar or
                self.para_text_ar or self.article_text_ar or
                self.extra_level_ar or "").strip()

    @property
    def hierarchy_level(self) -> str:
        """Determine the hierarchy level of this row."""
        if self.point_ref is not None:
            return "point"
        if self.item_num is not None:
            return "item"
        if self.para_num is not None:
            return "para"
        if self.article_num is not None:
            return "article"
        if self.extra_level_en or self.extra_level_ar:
            return "part"
        return "unknown"

    @property
    def section_number(self) -> Optional[str]:
        """Build hierarchical section number from available components."""
        parts = []
        if self.article_num is not None:
            parts.append(str(self.article_num))
        if self.para_num is not None:
            parts.append(str(self.para_num))
        if self.item_num is not None:
            parts.append(str(self.item_num))
        if self.point_ref is not None:
            parts.append(str(self.point_ref))
        return ".".join(parts) if parts else None

    def compute_hash(self) -> str:
        """SHA-256 hash of content for change detection."""
        content = f"{self.best_text_en}|{self.best_text_ar}|{self.section_number}|{self.applied}"
        self.content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        return self.content_hash


def _safe_str(val) -> str:
    """Convert a cell value to a clean string."""
    if val is None:
        return ""
    s = str(val).strip()
    return s if s else ""


def _safe_num(val) -> Optional[str]:
    """Convert a cell value to a hierarchy number string, or None."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _find_column_indices(header: list) -> dict:
    """Detect column mapping from header row.

    Returns a dict mapping semantic role → column index.
    Handles the various layouts found across the 27 sheets.
    """
    mapping = {}
    header_lower = [str(h).lower().strip() if h else "" for h in header]

    # Build a lookup of header keywords to column indices
    for i, h in enumerate(header_lower):
        if not h:
            continue

        # English hierarchy columns
        if h == "article" and "en_article_num" not in mapping:
            mapping["en_article_num"] = i
        elif h in ("article text", "article text "):
            mapping["en_article_text"] = i
        elif h == "para":
            mapping["en_para_num"] = i
        elif h == "para text":
            mapping["en_para_text"] = i
        elif h == "item":
            mapping["en_item_num"] = i
        elif h in ("item text", "item text "):
            mapping["en_item_text"] = i
        elif h == "point":
            mapping["en_point_ref"] = i
        elif h in ("point text", "point text "):
            mapping["en_point_text"] = i

        # Extra hierarchy (Part, Section, Contents)
        elif h in ("part", "parts"):
            mapping["en_extra_num"] = i
        elif h in ("part text", "part text "):
            mapping["en_extra_text"] = i
        elif h in ("section", "ٍثؤفهخىsection"):  # Actuarial has garbled prefix
            mapping["en_section_num"] = i
        elif h in ("section text",):
            mapping["en_section_text"] = i
        elif h == "contents":
            mapping["en_contents"] = i

        # Applied status
        elif "مطبقة" in h or "applied" in h:
            mapping["applied"] = i

        # Arabic hierarchy columns
        elif h == "المادة" or h == " المادة":
            mapping["ar_article_num"] = i
        elif h == "نص المادة":
            mapping["ar_article_text"] = i
        elif h == "الفقرة":
            mapping["ar_para_num"] = i
        elif h == "نص الفقرة":
            mapping["ar_para_text"] = i
        elif h == "البند":
            mapping["ar_item_num"] = i
        elif h == "نص البند":
            mapping["ar_item_text"] = i
        elif h == "نقطة":
            mapping["ar_point_ref"] = i
        elif h == "نص النقطة":
            mapping["ar_point_text"] = i
        elif h == "الباب":
            mapping["ar_extra_num"] = i
        elif h == "نص الباب":
            mapping["ar_extra_text"] = i
        elif h == "الجزء":
            mapping["ar_part_num"] = i
        elif h == "نص الجزء":
            mapping["ar_part_text"] = i
        elif h == "الفصل":
            mapping["ar_section_num"] = i
        elif h == "نص الفصل":
            mapping["ar_section_text"] = i

    return mapping


def _parse_sheet(ws, sheet_name: str) -> list[ParsedRow]:
    """Parse a single worksheet into a list of ParsedRow objects."""
    rows_iter = ws.iter_rows(values_only=True)

    # First row is the header
    try:
        header = list(next(rows_iter))
    except StopIteration:
        return []

    col_map = _find_column_indices(header)
    if not col_map:
        logger.warning(f"Could not detect column layout for sheet: {sheet_name!r}")
        return []

    def _get(vals: list, key: str):
        idx = col_map.get(key)
        if idx is None or idx >= len(vals):
            return None
        return vals[idx]

    parsed_rows: list[ParsedRow] = []
    for row_num, raw_row in enumerate(rows_iter, start=2):
        vals = list(raw_row)

        # Pad to ensure we don't index out of bounds
        while len(vals) < len(header) + 5:
            vals.append(None)

        row = ParsedRow(sheet_name=sheet_name, row_number=row_num)

        # English hierarchy
        row.article_num = _safe_num(_get(vals, "en_article_num"))
        row.article_text_en = _safe_str(_get(vals, "en_article_text"))
        row.para_num = _safe_num(_get(vals, "en_para_num"))
        row.para_text_en = _safe_str(_get(vals, "en_para_text"))
        row.item_num = _safe_num(_get(vals, "en_item_num"))
        row.item_text_en = _safe_str(_get(vals, "en_item_text"))
        row.point_ref = _safe_num(_get(vals, "en_point_ref"))
        row.point_text_en = _safe_str(_get(vals, "en_point_text"))

        # Extra levels (Part, Section, Contents)
        extra_en = (_safe_str(_get(vals, "en_extra_text"))
                    or _safe_str(_get(vals, "en_section_text"))
                    or _safe_str(_get(vals, "en_contents")))
        row.extra_level_en = extra_en

        # Applied
        row.applied = _safe_str(_get(vals, "applied")) or None

        # Arabic hierarchy
        ar_article_num = _safe_num(_get(vals, "ar_article_num"))
        row.article_text_ar = _safe_str(_get(vals, "ar_article_text"))
        ar_para_num = _safe_num(_get(vals, "ar_para_num"))
        row.para_text_ar = _safe_str(_get(vals, "ar_para_text"))
        ar_item_num = _safe_num(_get(vals, "ar_item_num"))
        row.item_text_ar = _safe_str(_get(vals, "ar_item_text"))
        ar_point_ref = _safe_num(_get(vals, "ar_point_ref"))
        row.point_text_ar = _safe_str(_get(vals, "ar_point_text"))

        # Extra Arabic levels
        ar_extra = (_safe_str(_get(vals, "ar_extra_text"))
                    or _safe_str(_get(vals, "ar_part_text"))
                    or _safe_str(_get(vals, "ar_section_text")))
        row.extra_level_ar = ar_extra

        # If EN hierarchy nums are empty but AR nums exist, use AR nums
        if row.article_num is None and ar_article_num is not None:
            row.article_num = ar_article_num
        if row.para_num is None and ar_para_num is not None:
            row.para_num = ar_para_num
        if row.item_num is None and ar_item_num is not None:
            row.item_num = ar_item_num
        if row.point_ref is None and ar_point_ref is not None:
            row.point_ref = ar_point_ref

        # Also check applied in last few columns if not found via header
        if row.applied is None:
            for v in reversed(vals):
                sv = _safe_str(v)
                if sv.lower() in ("yes", "no", "n/a"):
                    row.applied = sv
                    break

        # Skip completely empty rows
        if not row.best_text_en and not row.best_text_ar:
            continue

        # Classify the row
        row.row_class = _classify_text(row.best_text_en, row.best_text_ar)
        row.compute_hash()

        parsed_rows.append(row)

    return parsed_rows


def parse_excel(excel_path: Optional[str] = None) -> dict[str, list[ParsedRow]]:
    """Parse the entire IA Excel file.

    Returns: {sheet_name: [ParsedRow, ...]}
    """
    path = Path(excel_path) if excel_path else _DEFAULT_EXCEL_PATH
    if not path.exists():
        raise FileNotFoundError(f"IA regulations Excel not found at {path}")

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    result: dict[str, list[ParsedRow]] = {}

    for sheet_name in wb.sheetnames:
        if sheet_name == "Empty table":
            continue
        try:
            ws = wb[sheet_name]
            rows = _parse_sheet(ws, sheet_name)
            if rows:
                result[sheet_name] = rows
        except Exception as e:
            logger.error(f"Failed to parse sheet {sheet_name!r}: {e}")

    wb.close()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Classification Statistics
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SheetStats:
    """Import statistics for a single sheet."""
    sheet_name: str
    doc_key: str = ""
    total_rows: int = 0
    headings: int = 0
    definitions: int = 0
    obligations: int = 0
    prohibitions: int = 0
    penalties: int = 0
    reporting: int = 0
    guidance: int = 0
    descriptive: int = 0
    metadata_skipped: int = 0
    provisions_created: int = 0
    obligations_created: int = 0
    bilingual_rows: int = 0
    arabic_only_rows: int = 0
    english_only_rows: int = 0

    def to_dict(self) -> dict:
        return {
            "sheet_name": self.sheet_name,
            "doc_key": self.doc_key,
            "total_rows": self.total_rows,
            "classification": {
                "headings": self.headings,
                "definitions": self.definitions,
                "obligations": self.obligations,
                "prohibitions": self.prohibitions,
                "penalties": self.penalties,
                "reporting": self.reporting,
                "guidance": self.guidance,
                "descriptive": self.descriptive,
                "metadata_skipped": self.metadata_skipped,
            },
            "created": {
                "provisions": self.provisions_created,
                "obligations": self.obligations_created,
            },
            "language_coverage": {
                "bilingual": self.bilingual_rows,
                "arabic_only": self.arabic_only_rows,
                "english_only": self.english_only_rows,
            },
        }


def _update_stats(stats: SheetStats, row: ParsedRow):
    """Update sheet stats from a parsed row."""
    stats.total_rows += 1
    class_map = {
        RowClass.HEADING: "headings",
        RowClass.DEFINITION: "definitions",
        RowClass.OBLIGATION: "obligations",
        RowClass.PROHIBITION: "prohibitions",
        RowClass.PENALTY: "penalties",
        RowClass.REPORTING: "reporting",
        RowClass.GUIDANCE: "guidance",
        RowClass.DESCRIPTIVE: "descriptive",
        RowClass.METADATA: "metadata_skipped",
    }
    attr = class_map.get(row.row_class, "metadata_skipped")
    setattr(stats, attr, getattr(stats, attr) + 1)

    has_en = bool(row.best_text_en)
    has_ar = bool(row.best_text_ar)
    if has_en and has_ar:
        stats.bilingual_rows += 1
    elif has_ar:
        stats.arabic_only_rows += 1
    elif has_en:
        stats.english_only_rows += 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Reconciliation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReconciliationResult:
    """Result of reconciling spreadsheet data against existing DB records."""
    new_documents: list[str] = field(default_factory=list)
    existing_documents: list[str] = field(default_factory=list)
    new_provisions: int = 0
    changed_provisions: int = 0
    unchanged_provisions: int = 0
    missing_from_spreadsheet: int = 0  # in DB but not in spreadsheet
    duplicate_provisions: int = 0
    conflicts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "new_documents": self.new_documents,
            "existing_documents": self.existing_documents,
            "new_provisions": self.new_provisions,
            "changed_provisions": self.changed_provisions,
            "unchanged_provisions": self.unchanged_provisions,
            "missing_from_spreadsheet": self.missing_from_spreadsheet,
            "duplicate_provisions": self.duplicate_provisions,
            "conflicts": self.conflicts[:50],  # Cap for API response size
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Main Service
# ═══════════════════════════════════════════════════════════════════════════════

class IAExcelService:
    """Full lifecycle service for IA regulation data."""

    # ── Parsing ─────────────────────────────────────────────────────────
    @staticmethod
    def parse(excel_path: Optional[str] = None) -> dict[str, list[ParsedRow]]:
        """Parse the Excel file and return classified rows per sheet."""
        return parse_excel(excel_path)

    @staticmethod
    def get_parse_summary(parsed: dict[str, list[ParsedRow]]) -> dict:
        """Return a summary of parsed data."""
        all_stats: list[SheetStats] = []
        for sheet_name, rows in parsed.items():
            stats = SheetStats(sheet_name=sheet_name)
            for row in rows:
                _update_stats(stats, row)
            all_stats.append(stats)

        total_rows = sum(s.total_rows for s in all_stats)
        total_obligations = sum(
            s.obligations + s.prohibitions + s.penalties + s.reporting + s.guidance
            for s in all_stats
        )
        return {
            "sheets_parsed": len(all_stats),
            "total_rows": total_rows,
            "total_obligation_rows": total_obligations,
            "total_non_obligation_rows": total_rows - total_obligations,
            "sheets": [s.to_dict() for s in all_stats],
        }

    # ── Seeding (full chain) ───────────────────────────────────────────
    @staticmethod
    async def seed(
        db: AsyncSession,
        excel_path: Optional[str] = None,
        force_update: bool = False,
    ) -> dict:
        """Parse Excel and seed Source → Document → Provision → Obligation.

        This is idempotent: re-running will skip existing documents unless
        force_update=True, in which case changed provisions are flagged
        but never silently overwritten.

        Returns detailed stats and reconciliation report.
        """
        parsed = parse_excel(excel_path)

        # Look up IA regulator and SA jurisdiction
        regulator = await _get_regulator(db, "IA")
        jurisdiction = await _get_jurisdiction(db, "SA")

        # Build sheet→doc mapping
        sheet_to_doc = {doc["sheet"]: doc for doc in IA_DOCUMENTS}

        all_sheet_stats: list[dict] = []
        recon = ReconciliationResult()
        total_provisions = 0
        total_obligations = 0

        for sheet_name, rows in parsed.items():
            doc_def = sheet_to_doc.get(sheet_name)
            if not doc_def:
                logger.warning(f"No IA_DOCUMENTS entry for sheet: {sheet_name!r} — skipping")
                continue

            stats = SheetStats(sheet_name=sheet_name, doc_key=doc_def["key"])
            for row in rows:
                _update_stats(stats, row)

            # Check for existing document
            doc_title = f"IA - {doc_def['title']}"
            result = await db.execute(
                select(RegulatoryDocument).where(
                    RegulatoryDocument.title == doc_title,
                    RegulatoryDocument.regulator_id == regulator.id,
                )
            )
            existing_doc = result.scalar_one_or_none()

            if existing_doc and not force_update:
                recon.existing_documents.append(doc_title)
                # Count existing provisions for reconciliation
                prov_count_result = await db.execute(
                    select(func.count(Provision.id)).where(
                        Provision.document_id == existing_doc.id
                    )
                )
                existing_prov_count = prov_count_result.scalar() or 0
                recon.unchanged_provisions += existing_prov_count
                stats.provisions_created = 0
                stats.obligations_created = 0
                all_sheet_stats.append(stats.to_dict())
                continue

            if existing_doc and force_update:
                # Reconcile: compare existing vs new, report changes
                sheet_recon = await _reconcile_sheet(
                    db, existing_doc, rows, doc_def
                )
                recon.existing_documents.append(doc_title)
                recon.changed_provisions += sheet_recon["changed"]
                recon.unchanged_provisions += sheet_recon["unchanged"]
                recon.missing_from_spreadsheet += sheet_recon["missing_from_spreadsheet"]
                recon.conflicts.extend(sheet_recon["conflicts"])
                all_sheet_stats.append(stats.to_dict())
                continue

            # New document — create full chain
            recon.new_documents.append(doc_title)

            # Find the Source record and link via SourceVersion for provenance
            source = await _find_source(db, regulator.id, doc_def["key"])
            source_version_id = None
            if source:
                # Look up or create a SourceVersion so the document links
                # back to Source (needed for risk scoring authority_level)
                sv_result = await db.execute(
                    select(SourceVersion).where(
                        SourceVersion.source_id == source.id,
                        SourceVersion.is_current == True,  # noqa: E712
                    )
                )
                sv = sv_result.scalar_one_or_none()
                if not sv:
                    from datetime import datetime, timezone
                    sv = SourceVersion(
                        id=generate_uuid(),
                        source_id=source.id,
                        version_number=1,
                        fetched_at=datetime.now(timezone.utc),
                        content_hash=hashlib.sha256(
                            f"ia_regulations.xlsx:{doc_def['key']}".encode()
                        ).hexdigest(),
                        is_current=True,
                        parser_confidence=0.95,
                    )
                    db.add(sv)
                    await db.flush()
                source_version_id = sv.id

            doc = RegulatoryDocument(
                title=doc_title,
                title_ar=doc_def["title_ar"],
                document_type=doc_def.get("source_type", "regulation"),
                regulator_id=regulator.id,
                jurisdiction_id=jurisdiction.id,
                language="ar+en",
                status=DocumentStatus.ACTIVE,
                source_version_id=source_version_id,
                summary=f"Insurance Authority: {doc_def['title']}",
                summary_ar=f"هيئة التأمين: {doc_def['title_ar']}",
                metadata_extra={
                    "pack_id": "insurance_authority",
                    "source_key": doc_def["key"],
                    "sheet_name": sheet_name,
                    "import_source": "ia_regulations.xlsx",
                    "row_count": len(rows),
                },
            )
            db.add(doc)
            await db.flush()

            # Create provisions and obligations for each row
            provisions_created = 0
            obligations_created = 0
            seen_hashes: set[str] = set()

            for i, row in enumerate(rows):
                # Skip metadata rows
                if row.row_class == RowClass.METADATA:
                    continue

                # Deduplicate by content hash within the same document
                if row.content_hash in seen_hashes:
                    recon.duplicate_provisions += 1
                    continue
                seen_hashes.add(row.content_hash)

                # Determine provision type
                prov_type = _ROW_TO_PROVISION_TYPE.get(
                    row.row_class, _hierarchy_to_prov_type(row.hierarchy_level)
                )

                text_en = row.best_text_en
                text_ar = row.best_text_ar

                # Provision text: prefer EN, fallback to AR
                prov_text = text_en if text_en else text_ar

                prov = Provision(
                    document_id=doc.id,
                    section_number=row.section_number,
                    title=(text_en[:500] if text_en else text_ar[:500]) if row.hierarchy_level in ("article", "part") else None,
                    title_ar=(text_ar[:500] if text_ar and row.hierarchy_level in ("article", "part") else None),
                    text=prov_text,
                    text_ar=text_ar if text_ar else None,
                    provision_type=prov_type,
                    order_index=i,
                )
                db.add(prov)
                await db.flush()
                provisions_created += 1
                recon.new_provisions += 1

                # Create obligation if this row type warrants it
                if _CREATES_OBLIGATION.get(row.row_class, False):
                    ob_type = _ROW_TO_OBLIGATION_TYPE.get(
                        row.row_class, ObligationType.MANDATORY
                    )
                    criticality = _infer_criticality(row.row_class, text_en, text_ar)
                    confidence = _infer_confidence(row)

                    obligation = Obligation(
                        provision_id=prov.id,
                        text=prov_text,
                        text_ar=text_ar if text_ar else None,
                        normalized_summary=_make_summary(text_en, text_ar),
                        normalized_summary_ar=_make_summary_ar(text_ar, text_en),
                        obligation_type=ob_type,
                        applies_to_entity_types=["insurance"],
                        extraction_method=ExtractionMethod.RULE_BASED,
                        review_status=ReviewStatus.PENDING,
                        confidence=confidence,
                        criticality=criticality,
                        is_active=True,
                        version=1,
                    )
                    db.add(obligation)
                    obligations_created += 1

            await db.flush()
            total_provisions += provisions_created
            total_obligations += obligations_created
            stats.provisions_created = provisions_created
            stats.obligations_created = obligations_created
            all_sheet_stats.append(stats.to_dict())

            logger.info(
                f"Seeded {doc_title}: {provisions_created} provisions, "
                f"{obligations_created} obligations"
            )

        return {
            "status": "completed",
            "documents_created": len(recon.new_documents),
            "documents_existing": len(recon.existing_documents),
            "total_provisions_created": total_provisions,
            "total_obligations_created": total_obligations,
            "reconciliation": recon.to_dict(),
            "sheets": all_sheet_stats,
        }

    # ── Reconciliation (compare spreadsheet vs DB) ─────────────────────
    @staticmethod
    async def reconcile(
        db: AsyncSession,
        excel_path: Optional[str] = None,
    ) -> dict:
        """Compare spreadsheet content against existing DB records.

        Does NOT modify any data — read-only comparison.
        """
        parsed = parse_excel(excel_path)
        regulator = await _get_regulator(db, "IA")
        sheet_to_doc = {doc["sheet"]: doc for doc in IA_DOCUMENTS}

        recon = ReconciliationResult()

        for sheet_name, rows in parsed.items():
            doc_def = sheet_to_doc.get(sheet_name)
            if not doc_def:
                continue

            doc_title = f"IA - {doc_def['title']}"
            result = await db.execute(
                select(RegulatoryDocument).where(
                    RegulatoryDocument.title == doc_title,
                    RegulatoryDocument.regulator_id == regulator.id,
                )
            )
            existing_doc = result.scalar_one_or_none()

            if not existing_doc:
                recon.new_documents.append(doc_title)
                recon.new_provisions += len([r for r in rows if r.row_class != RowClass.METADATA])
                continue

            recon.existing_documents.append(doc_title)
            sheet_recon = await _reconcile_sheet(db, existing_doc, rows, doc_def)
            recon.new_provisions += sheet_recon.get("new", 0)
            recon.changed_provisions += sheet_recon["changed"]
            recon.unchanged_provisions += sheet_recon["unchanged"]
            recon.missing_from_spreadsheet += sheet_recon["missing_from_spreadsheet"]
            recon.conflicts.extend(sheet_recon["conflicts"])

        return recon.to_dict()

    # ── Stats ──────────────────────────────────────────────────────────
    @staticmethod
    async def get_ia_stats(db: AsyncSession) -> dict:
        """Return current IA regulation stats from the database."""
        regulator = await _get_regulator(db, "IA")

        result = await db.execute(
            select(RegulatoryDocument).where(
                RegulatoryDocument.regulator_id == regulator.id
            )
        )
        docs = result.scalars().all()

        total_provisions = 0
        total_obligations = 0
        doc_summaries = []

        for doc in docs:
            prov_result = await db.execute(
                select(func.count(Provision.id)).where(
                    Provision.document_id == doc.id
                )
            )
            prov_count = prov_result.scalar() or 0

            ob_result = await db.execute(
                select(func.count(Obligation.id))
                .join(Provision, Obligation.provision_id == Provision.id)
                .where(Provision.document_id == doc.id)
            )
            ob_count = ob_result.scalar() or 0

            total_provisions += prov_count
            total_obligations += ob_count

            doc_summaries.append({
                "id": doc.id,
                "title": doc.title,
                "title_ar": doc.title_ar,
                "document_type": doc.document_type,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                "provisions_count": prov_count,
                "obligations_count": ob_count,
            })

        return {
            "regulator": regulator.name,
            "regulator_ar": regulator.name_ar,
            "documents_count": len(docs),
            "total_provisions": total_provisions,
            "total_obligations": total_obligations,
            "documents": doc_summaries,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_regulator(db: AsyncSession, abbreviation: str) -> Regulator:
    result = await db.execute(
        select(Regulator).where(Regulator.abbreviation == abbreviation)
    )
    reg = result.scalar_one_or_none()
    if not reg:
        raise ValueError(
            f"{abbreviation} regulator not found — run POST /api/regulatory/seed first"
        )
    return reg


async def _get_jurisdiction(db: AsyncSession, code: str) -> Jurisdiction:
    result = await db.execute(
        select(Jurisdiction).where(Jurisdiction.code == code)
    )
    jur = result.scalar_one_or_none()
    if not jur:
        raise ValueError(f"Jurisdiction {code} not found — run POST /api/regulatory/seed first")
    return jur


async def _find_source(
    db: AsyncSession, regulator_id: str, source_key: str
) -> Optional[Source]:
    """Find the Source record for a given IA document key."""
    seed_key = f"insurance_authority:{source_key}"
    result = await db.execute(
        select(Source).where(Source.seed_key == seed_key)
    )
    return result.scalar_one_or_none()


async def _reconcile_sheet(
    db: AsyncSession,
    existing_doc: RegulatoryDocument,
    rows: list[ParsedRow],
    doc_def: dict,
) -> dict:
    """Reconcile a single sheet's rows against an existing document."""
    result = await db.execute(
        select(Provision).where(Provision.document_id == existing_doc.id)
    )
    existing_provs = list(result.scalars().all())

    # Build lookup of existing provisions by section_number
    existing_by_section: dict[str, Provision] = {}
    for prov in existing_provs:
        if prov.section_number:
            existing_by_section[prov.section_number] = prov

    # Track which existing provisions were matched
    matched_existing = set()
    changed = 0
    unchanged = 0
    new_count = 0
    conflicts: list[dict] = []

    for row in rows:
        if row.row_class == RowClass.METADATA:
            continue

        section = row.section_number
        if section and section in existing_by_section:
            prov = existing_by_section[section]
            matched_existing.add(prov.id)

            # Compare content
            new_text = row.best_text_en or row.best_text_ar
            old_text = prov.text or ""
            new_ar = row.best_text_ar
            old_ar = prov.text_ar or ""

            # Simple content change detection
            if new_text.strip() != old_text.strip() or new_ar.strip() != old_ar.strip():
                changed += 1
                conflicts.append({
                    "type": "content_changed",
                    "document": existing_doc.title,
                    "section": section,
                    "old_text_preview": old_text[:100],
                    "new_text_preview": new_text[:100],
                })
            else:
                unchanged += 1
        else:
            new_count += 1

    missing = len(existing_provs) - len(matched_existing)

    return {
        "new": new_count,
        "changed": changed,
        "unchanged": unchanged,
        "missing_from_spreadsheet": missing,
        "conflicts": conflicts,
    }


def _hierarchy_to_prov_type(level: str) -> ProvisionType:
    """Map hierarchy level to provision type."""
    return {
        "article": ProvisionType.ARTICLE,
        "para": ProvisionType.SECTION,
        "item": ProvisionType.CLAUSE,
        "point": ProvisionType.CLAUSE,
        "part": ProvisionType.CHAPTER,
        "unknown": ProvisionType.ARTICLE,
    }.get(level, ProvisionType.ARTICLE)


def _infer_criticality(row_class: RowClass, text_en: str, text_ar: str) -> str:
    """Infer obligation criticality from classification and content."""
    if row_class == RowClass.PENALTY:
        return "critical"
    if row_class == RowClass.PROHIBITION:
        return "high"
    if row_class == RowClass.REPORTING:
        return "high"
    if row_class == RowClass.GUIDANCE:
        return "low"

    # Check for high-criticality keywords
    combined = f"{text_en} {text_ar}".lower()
    high_keywords = [
        "aml", "anti-money", "terrorist", "sanctions", "suspicious",
        "غسل الأموال", "تمويل الإرهاب", "عقوبات", "مشتبه",
    ]
    for kw in high_keywords:
        if kw in combined:
            return "high"

    return "medium"


def _infer_confidence(row: ParsedRow) -> float:
    """Infer extraction confidence based on row characteristics."""
    base = 0.70

    # Bilingual rows are higher confidence (cross-reference)
    if row.best_text_en and row.best_text_ar:
        base += 0.10

    # Rows with clear section numbers are more structured
    if row.section_number:
        base += 0.05

    # Applied status available
    if row.applied:
        base += 0.05

    # Certain classifications have higher inherent confidence
    confident_classes = {RowClass.OBLIGATION, RowClass.PROHIBITION, RowClass.PENALTY}
    if row.row_class in confident_classes:
        base += 0.05

    return min(base, 0.95)


def _make_summary(text_en: str, text_ar: str) -> str:
    """Create a normalised English summary."""
    text = text_en or text_ar
    if not text:
        return ""
    text = text.strip()
    # Remove leading connectors
    text = re.sub(r'^(?:and |or |also |furthermore )', '', text, flags=re.IGNORECASE)
    if len(text) > 300:
        for sep in ['; ', ', ', ' — ', ' - ']:
            idx = text.find(sep, 100)
            if 100 < idx < 300:
                text = text[:idx]
                break
        else:
            text = text[:300].rsplit(' ', 1)[0] + '...'
    return text


def _make_summary_ar(text_ar: str, text_en: str) -> Optional[str]:
    """Create a normalised Arabic summary."""
    text = text_ar or text_en
    if not text:
        return None
    text = text.strip()
    if len(text) > 300:
        text = text[:300].rsplit(' ', 1)[0] + '...'
    return text
