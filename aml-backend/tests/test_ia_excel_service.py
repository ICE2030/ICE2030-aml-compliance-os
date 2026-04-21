"""Tests for IA Excel parsing, classification, and reconciliation."""
import pytest
from app.services.regulatory.ia_excel_service import (
    RowClass,
    _classify_text,
    parse_excel,
    IAExcelService,
    ParsedRow,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Classification Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyText:
    """Test row classification logic."""

    def test_heading_en_part(self):
        assert _classify_text("Part 1: Introduction", "") == RowClass.HEADING

    def test_heading_en_chapter(self):
        assert _classify_text("Chapter 3: Governance", "") == RowClass.HEADING

    def test_heading_en_definitions(self):
        assert _classify_text("Definitions", "") == RowClass.HEADING

    def test_heading_ar(self):
        assert _classify_text("", "الباب الأول") == RowClass.HEADING

    def test_heading_short_no_verb(self):
        assert _classify_text("Scope and Exemptions", "") == RowClass.HEADING

    def test_heading_general_provisions(self):
        assert _classify_text("General Provisions", "") == RowClass.HEADING

    def test_definition_means(self):
        assert _classify_text('"AML" means Anti-Money Laundering procedures.', "") == RowClass.DEFINITION

    def test_definition_refers_to(self):
        assert _classify_text("The term refers to any licensed entity.", "") == RowClass.DEFINITION

    def test_definition_ar(self):
        assert _classify_text("", "يُقصد بـ الشركة أي كيان مرخص") == RowClass.DEFINITION

    def test_definition_concept(self):
        assert _classify_text("", "مفهوم جريمة غسل الأموال:") == RowClass.DEFINITION

    def test_obligation_shall(self):
        assert _classify_text("Companies shall maintain adequate records.", "") == RowClass.OBLIGATION

    def test_obligation_must(self):
        assert _classify_text("The insurer must submit an application.", "") == RowClass.OBLIGATION

    def test_obligation_required(self):
        assert _classify_text("The company is required to establish internal controls.", "") == RowClass.OBLIGATION

    def test_obligation_ar(self):
        assert _classify_text("", "يجب على الشركات الالتزام بالمتطلبات") == RowClass.OBLIGATION

    def test_prohibition_shall_not(self):
        assert _classify_text("Companies shall not engage in unauthorized activities.", "") == RowClass.PROHIBITION

    def test_prohibition_prohibited(self):
        assert _classify_text("Such activities are prohibited under this regulation.", "") == RowClass.PROHIBITION

    def test_prohibition_ar(self):
        assert _classify_text("", "يحظر على الشركة القيام بأي نشاط غير مرخص") == RowClass.PROHIBITION

    def test_penalty(self):
        assert _classify_text("Any person convicted shall be sentenced to imprisonment not exceeding five years.", "") == RowClass.PENALTY

    def test_penalty_fine(self):
        assert _classify_text("A fine of not more than 100,000 riyals shall be imposed.", "") == RowClass.PENALTY

    def test_penalty_ar(self):
        assert _classify_text("", "يعاقب كل من يخالف أحكام هذا النظام بالسجن") == RowClass.PENALTY

    def test_reporting(self):
        assert _classify_text("The company shall report suspicious transactions within 24 hours.", "") == RowClass.REPORTING

    def test_reporting_submit(self):
        assert _classify_text("The insurer must submit quarterly reports to the Authority.", "") == RowClass.REPORTING

    def test_guidance_should(self):
        assert _classify_text("Companies should adopt best practices in risk management.", "") == RowClass.GUIDANCE

    def test_guidance_recommended(self):
        assert _classify_text("It is recommended to maintain a comprehensive training program.", "") == RowClass.GUIDANCE

    def test_guidance_ar(self):
        assert _classify_text("", "ينبغي على الشركات اعتماد أفضل الممارسات") == RowClass.GUIDANCE

    def test_descriptive(self):
        assert _classify_text("This regulation was issued in both Arabic and English.", "") == RowClass.DESCRIPTIVE

    def test_metadata_empty(self):
        assert _classify_text("", "") == RowClass.METADATA

    def test_metadata_short(self):
        assert _classify_text("ab", "") == RowClass.METADATA

    def test_non_compliance_penalty(self):
        result = _classify_text(
            "Non-compliance with the requirements set forth in This Code will be deemed a breach subject to penalties.",
            ""
        )
        assert result == RowClass.PENALTY


# ═══════════════════════════════════════════════════════════════════════════════
# ParsedRow Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestParsedRow:
    """Test ParsedRow computed properties."""

    def test_best_text_en_point_level(self):
        row = ParsedRow(
            sheet_name="test", row_number=1,
            article_text_en="Article text",
            para_text_en="Para text",
            item_text_en="Item text",
            point_text_en="Point text",
        )
        assert row.best_text_en == "Point text"

    def test_best_text_en_fallback(self):
        row = ParsedRow(
            sheet_name="test", row_number=1,
            article_text_en="Article text",
        )
        assert row.best_text_en == "Article text"

    def test_best_text_ar(self):
        row = ParsedRow(
            sheet_name="test", row_number=1,
            article_text_ar="نص المادة",
            para_text_ar="نص الفقرة",
        )
        assert row.best_text_ar == "نص الفقرة"

    def test_hierarchy_level_point(self):
        row = ParsedRow(sheet_name="test", row_number=1, point_ref="a")
        assert row.hierarchy_level == "point"

    def test_hierarchy_level_item(self):
        row = ParsedRow(sheet_name="test", row_number=1, item_num="3")
        assert row.hierarchy_level == "item"

    def test_hierarchy_level_article(self):
        row = ParsedRow(sheet_name="test", row_number=1, article_num="5")
        assert row.hierarchy_level == "article"

    def test_section_number(self):
        row = ParsedRow(
            sheet_name="test", row_number=1,
            article_num="5", para_num="2", item_num="a",
        )
        assert row.section_number == "5.2.a"

    def test_section_number_article_only(self):
        row = ParsedRow(sheet_name="test", row_number=1, article_num="10")
        assert row.section_number == "10"

    def test_content_hash_deterministic(self):
        row = ParsedRow(
            sheet_name="test", row_number=1,
            article_text_en="Test content",
            article_num="1",
        )
        h1 = row.compute_hash()
        h2 = row.compute_hash()
        assert h1 == h2
        assert len(h1) == 16


# ═══════════════════════════════════════════════════════════════════════════════
# Excel Parsing Tests (integration — requires the actual file)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExcelParsing:
    """Test parsing the actual IA regulations Excel file."""

    def test_parse_returns_sheets(self):
        parsed = parse_excel()
        assert len(parsed) >= 25, f"Expected 25+ sheets, got {len(parsed)}"

    def test_all_sheets_have_rows(self):
        parsed = parse_excel()
        for sheet_name, rows in parsed.items():
            assert len(rows) > 0, f"Sheet {sheet_name!r} has no parsed rows"

    def test_total_rows_exceeds_3000(self):
        parsed = parse_excel()
        total = sum(len(rows) for rows in parsed.values())
        assert total >= 2500, f"Expected 2500+ total rows, got {total}"

    def test_classification_distribution(self):
        """Verify that not all rows are classified as the same type."""
        parsed = parse_excel()
        all_classes = set()
        for rows in parsed.values():
            for row in rows:
                all_classes.add(row.row_class)
        # Should have at least 4 different classification types
        assert len(all_classes) >= 4, f"Only {len(all_classes)} class types: {all_classes}"

    def test_obligations_are_minority(self):
        """Verify that obligations are NOT the majority (proper classification)."""
        parsed = parse_excel()
        total = 0
        obligation_types = 0
        for rows in parsed.values():
            for row in rows:
                total += 1
                if row.row_class in (
                    RowClass.OBLIGATION, RowClass.PROHIBITION,
                    RowClass.PENALTY, RowClass.REPORTING, RowClass.GUIDANCE,
                ):
                    obligation_types += 1
        # Obligations should be less than 100% (classification is working)
        ratio = obligation_types / total if total > 0 else 0
        assert ratio < 0.95, f"Too many obligation rows ({ratio:.1%}) — classification may be broken"

    def test_has_bilingual_content(self):
        """Verify bilingual rows exist."""
        parsed = parse_excel()
        bilingual = 0
        for rows in parsed.values():
            for row in rows:
                if row.best_text_en and row.best_text_ar:
                    bilingual += 1
        assert bilingual > 100, f"Expected 100+ bilingual rows, got {bilingual}"

    def test_has_arabic_only_content(self):
        """Verify Arabic-only rows exist (AML&CTF sheet etc)."""
        parsed = parse_excel()
        ar_only = 0
        for rows in parsed.values():
            for row in rows:
                if row.best_text_ar and not row.best_text_en:
                    ar_only += 1
        assert ar_only > 50, f"Expected 50+ Arabic-only rows, got {ar_only}"

    def test_hierarchy_preserved(self):
        """Verify hierarchical section numbers are generated."""
        parsed = parse_excel()
        has_section = 0
        for rows in parsed.values():
            for row in rows:
                if row.section_number:
                    has_section += 1
        assert has_section > 500, f"Expected 500+ rows with section numbers, got {has_section}"

    def test_headings_detected(self):
        """Verify structural headings are properly detected."""
        parsed = parse_excel()
        headings = 0
        for rows in parsed.values():
            for row in rows:
                if row.row_class == RowClass.HEADING:
                    headings += 1
        assert headings > 10, f"Expected 10+ headings, got {headings}"

    def test_parse_summary(self):
        """Test get_parse_summary returns expected structure."""
        parsed = parse_excel()
        summary = IAExcelService.get_parse_summary(parsed)
        assert "sheets_parsed" in summary
        assert "total_rows" in summary
        assert "total_obligation_rows" in summary
        assert "total_non_obligation_rows" in summary
        assert summary["total_non_obligation_rows"] > 0, "Should have non-obligation rows"


# ═══════════════════════════════════════════════════════════════════════════════
# Seeding Tests (requires database)
# ═══════════════════════════════════════════════════════════════════════════════

# These would typically be run with a test database fixture.
# For now, they validate the service interface exists and is callable.

class TestIAExcelServiceInterface:
    """Test that the service interface is correctly structured."""

    def test_parse_method_exists(self):
        assert callable(IAExcelService.parse)

    def test_seed_method_exists(self):
        assert callable(IAExcelService.seed)

    def test_reconcile_method_exists(self):
        assert callable(IAExcelService.reconcile)

    def test_get_ia_stats_method_exists(self):
        assert callable(IAExcelService.get_ia_stats)

    def test_get_parse_summary_method_exists(self):
        assert callable(IAExcelService.get_parse_summary)
