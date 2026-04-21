"""Regression tests for pre-Phase-4 hardening pass.

Fix 1: Bridge Phase 1 -> Phase 3 decisions
Fix 2: Penalty provision classification (reclassify penalty language in mandatory)
Fix 3: Trailing slash POST redirect
Fix 4: CaseType enum expansion
Fix 5: Similarity threshold raised to 0.15
Fix 6: Dashboard resolution time uses _best_resolution_seconds
Fix 7: Overlapping obligation deduplication
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.regulatory.obligation_extraction_service import (
    RuleBasedExtractor,
    ExtractedObligation,
)
from app.services.intelligence_service import (
    _best_resolution_seconds,
    _cosine_similarity,
)
from app.models.case import CaseType


# ═══════════════════════════════════════════════════════════════════════
# Fix 1 — Bridge Phase 1 -> Phase 3 decisions
# ═══════════════════════════════════════════════════════════════════════

class TestDecisionBridge:
    """Fix 1: The Phase 1 decide_case endpoint must call DecisionCaptureService."""

    def test_cases_router_imports_decision_capture_service(self):
        """The cases router must import DecisionCaptureService."""
        from app.routers.cases import DecisionCaptureService
        assert DecisionCaptureService is not None

    def test_decide_case_calls_capture_decision(self):
        """Verify the decide_case function source contains capture_decision call."""
        import inspect
        from app.routers.cases import decide_case
        source = inspect.getsource(decide_case)
        assert "DecisionCaptureService.capture_decision" in source, \
            "decide_case must call DecisionCaptureService.capture_decision()"

    def test_decide_case_maps_ai_disposition(self):
        """Verify ai_disposition is derived from ai_suggestion_accepted."""
        import inspect
        from app.routers.cases import decide_case
        source = inspect.getsource(decide_case)
        assert "ai_disposition" in source, \
            "decide_case must map ai_suggestion_accepted to ai_disposition"


# ═══════════════════════════════════════════════════════════════════════
# Fix 2 — Penalty provision classification
# ═══════════════════════════════════════════════════════════════════════

class TestPenaltyReclassification:
    """Fix 2: Mandatory/prohibition patterns containing penalty language
    must be reclassified as 'penalty', not 'mandatory'."""

    def test_mandatory_with_imprisonment_becomes_penalty(self):
        """A 'shall' sentence about imprisonment should be penalty, not mandatory."""
        text = (
            "Any person who violates these provisions shall be punished "
            "with imprisonment for not more than ten years and a fine "
            "not exceeding five million riyals."
        )
        results = RuleBasedExtractor.extract(text)
        types = [r.obligation_type for r in results]
        assert "mandatory" not in types, \
            f"Penalty-language sentence wrongly classified as mandatory. Types: {types}"
        assert "penalty" in types, \
            f"Penalty-language sentence not classified as penalty. Types: {types}"

    def test_mandatory_with_fine_becomes_penalty(self):
        """A 'shall' sentence about fines should be penalty."""
        text = (
            "The institution shall be fined an amount not exceeding "
            "SAR 10,000,000 for each violation of this regulation."
        )
        results = RuleBasedExtractor.extract(text)
        types = [r.obligation_type for r in results]
        assert "mandatory" not in types, \
            f"Fine sentence wrongly classified as mandatory. Types: {types}"

    def test_genuine_mandatory_not_reclassified(self):
        """A genuine mandatory obligation must remain mandatory."""
        text = (
            "Financial institutions shall implement internal policies, "
            "procedures, and controls to prevent money laundering and "
            "terrorism financing activities."
        )
        results = RuleBasedExtractor.extract(text)
        types = [r.obligation_type for r in results]
        assert "mandatory" in types, \
            f"Genuine mandatory obligation lost. Types: {types}"
        assert "penalty" not in types, \
            f"Genuine mandatory wrongly reclassified as penalty. Types: {types}"

    def test_penalty_language_regex_compiled(self):
        """PENALTY_LANGUAGE_RE must be a compiled regex on RuleBasedExtractor."""
        assert hasattr(RuleBasedExtractor, 'PENALTY_LANGUAGE_RE')
        assert RuleBasedExtractor.PENALTY_LANGUAGE_RE.search("imprisonment")
        assert RuleBasedExtractor.PENALTY_LANGUAGE_RE.search("fine")
        assert RuleBasedExtractor.PENALTY_LANGUAGE_RE.search("عقوبة")
        assert not RuleBasedExtractor.PENALTY_LANGUAGE_RE.search("shall implement policies")


# ═══════════════════════════════════════════════════════════════════════
# Fix 3 — Trailing slash POST redirect
# ═══════════════════════════════════════════════════════════════════════

class TestTrailingSlashRouting:
    """Fix 3: POST to /api/cases (no slash) must not 307 redirect."""

    def test_app_redirect_slashes_disabled(self):
        """FastAPI app must have redirect_slashes=False."""
        from app.main import app
        assert app.router.redirect_slashes is False, \
            "FastAPI redirect_slashes must be False to prevent POST 307"

    def test_cases_router_has_both_slash_variants(self):
        """Cases router must register both '/' and '' for POST."""
        from app.main import app
        post_routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and 'POST' in route.methods:
                post_routes.append(route.path)
        # Both /api/cases/ and /api/cases should be present
        assert "/api/cases/" in post_routes, "Missing POST /api/cases/"
        assert "/api/cases" in post_routes, "Missing POST /api/cases (no slash)"

    def test_transactions_router_has_both_slash_variants(self):
        """Transactions router must register both '/' and '' for POST."""
        from app.main import app
        post_routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and 'POST' in route.methods:
                post_routes.append(route.path)
        assert "/api/transactions/" in post_routes
        assert "/api/transactions" in post_routes


# ═══════════════════════════════════════════════════════════════════════
# Fix 4 — CaseType enum expansion
# ═══════════════════════════════════════════════════════════════════════

class TestCaseTypeExpansion:
    """Fix 4: CaseType enum must include AML-specific case types."""

    def test_original_types_preserved(self):
        """Original 5 case types must still exist."""
        assert CaseType.SCREENING_MATCH.value == "screening_match"
        assert CaseType.TRANSACTION_ALERT.value == "transaction_alert"
        assert CaseType.MANUAL_REFERRAL.value == "manual_referral"
        assert CaseType.PERIODIC_REVIEW.value == "periodic_review"
        assert CaseType.RISK_ESCALATION.value == "risk_escalation"

    def test_new_aml_types_added(self):
        """New AML-specific case types must exist."""
        assert CaseType.AML_REVIEW.value == "aml_review"
        assert CaseType.CDD_REVIEW.value == "cdd_review"
        assert CaseType.SANCTIONS_REVIEW.value == "sanctions_review"
        assert CaseType.STR_FILING.value == "str_filing"

    def test_total_case_type_count(self):
        """CaseType should have 9 members (5 original + 4 new)."""
        assert len(CaseType) == 9


# ═══════════════════════════════════════════════════════════════════════
# Fix 5 — Similarity threshold raised
# ═══════════════════════════════════════════════════════════════════════

class TestSimilarityThreshold:
    """Fix 5: Similarity threshold must be raised from 0.05 to 0.15."""

    def test_threshold_in_source_code(self):
        """find_similar_cases must use threshold > 0.10."""
        import inspect
        from app.services.intelligence_service import CaseMemoryService
        source = inspect.getsource(CaseMemoryService.find_similar_cases)
        # Must NOT contain the old threshold
        assert "hybrid_score > 0.05" not in source, \
            "Old 0.05 threshold still present"
        assert "hybrid_score > 0.15" in source or "hybrid_score > 0.2" in source, \
            "New threshold (0.15 or 0.20) not found in find_similar_cases"


# ═══════════════════════════════════════════════════════════════════════
# Fix 6 — Dashboard resolution time calculation
# ═══════════════════════════════════════════════════════════════════════

class TestResolutionTimeCalculation:
    """Fix 6: Dashboard must use _best_resolution_seconds helper."""

    def test_best_resolution_prefers_breakdown(self):
        """When inv + review are provided, prefer them over wall-clock."""
        capture = MagicMock()
        capture.investigation_time_seconds = 120
        capture.review_time_seconds = 60
        capture.time_to_decision_seconds = 3600  # wall clock = 1hr
        assert _best_resolution_seconds(capture) == 180  # 120 + 60

    def test_best_resolution_falls_back_to_wall_clock(self):
        """When no breakdown, use time_to_decision_seconds."""
        capture = MagicMock()
        capture.investigation_time_seconds = None
        capture.review_time_seconds = None
        capture.time_to_decision_seconds = 3600
        assert _best_resolution_seconds(capture) == 3600

    def test_best_resolution_partial_breakdown(self):
        """When only investigation is provided, still use breakdown."""
        capture = MagicMock()
        capture.investigation_time_seconds = 300
        capture.review_time_seconds = 0
        capture.time_to_decision_seconds = 7200
        assert _best_resolution_seconds(capture) == 300

    def test_best_resolution_no_timing_returns_none(self):
        """When nothing is available, return None."""
        capture = MagicMock()
        capture.investigation_time_seconds = None
        capture.review_time_seconds = None
        capture.time_to_decision_seconds = None
        assert _best_resolution_seconds(capture) is None

    def test_efficiency_loop_uses_best_resolution(self):
        """Efficiency loop source must reference _best_resolution_seconds."""
        import inspect
        from app.services.intelligence_service import IntelligenceLoopService
        source = inspect.getsource(IntelligenceLoopService.compute_efficiency_loop)
        assert "_best_resolution_seconds" in source, \
            "Efficiency loop must use _best_resolution_seconds helper"


# ═══════════════════════════════════════════════════════════════════════
# Fix 7 — Overlapping obligation deduplication
# ═══════════════════════════════════════════════════════════════════════

class TestObligationDeduplication:
    """Fix 7: Overlapping obligations from the same sentence should be merged."""

    def test_deduplicate_removes_less_specific(self):
        """When two obligations have identical text, keep the more specific type."""
        ob1 = ExtractedObligation(
            text="Financial institutions shall identify the customer and verify identity.",
            obligation_type="mandatory",
            confidence=0.85,
        )
        ob2 = ExtractedObligation(
            text="Financial institutions shall identify the customer and verify identity.",
            obligation_type="identification",
            confidence=0.85,
        )
        result = RuleBasedExtractor._deduplicate_overlapping([ob1, ob2])
        assert len(result) == 1, f"Expected 1 after dedup, got {len(result)}"
        assert result[0].obligation_type == "identification", \
            "Should keep the more specific type (identification > mandatory)"

    def test_deduplicate_preserves_distinct(self):
        """Obligations with <80% overlap should both survive."""
        ob1 = ExtractedObligation(
            text="Financial institutions shall report suspicious transactions to SAFIU.",
            obligation_type="reporting",
            confidence=0.85,
        )
        ob2 = ExtractedObligation(
            text="All records must be maintained for at least five years after closure.",
            obligation_type="recordkeeping",
            confidence=0.80,
        )
        result = RuleBasedExtractor._deduplicate_overlapping([ob1, ob2])
        assert len(result) == 2, "Distinct obligations should both survive"

    def test_deduplicate_single_obligation(self):
        """A single obligation should pass through unchanged."""
        ob = ExtractedObligation(
            text="Shall implement AML controls and procedures.",
            obligation_type="mandatory",
            confidence=0.85,
        )
        result = RuleBasedExtractor._deduplicate_overlapping([ob])
        assert len(result) == 1

    def test_deduplicate_empty_list(self):
        """Empty list should return empty."""
        result = RuleBasedExtractor._deduplicate_overlapping([])
        assert result == []

    def test_deduplicate_penalty_wins_over_mandatory(self):
        """When penalty and mandatory overlap, penalty should win."""
        text = "The offender shall be sentenced to imprisonment and fined heavily."
        ob1 = ExtractedObligation(text=text, obligation_type="mandatory", confidence=0.85)
        ob2 = ExtractedObligation(text=text, obligation_type="penalty", confidence=0.80)
        result = RuleBasedExtractor._deduplicate_overlapping([ob1, ob2])
        assert len(result) == 1
        assert result[0].obligation_type == "penalty"

    def test_extract_deduplicates_cdd_overlaps(self):
        """Real-world CDD text should not produce duplicate obligations for same sentence."""
        text = (
            "Financial institutions shall identify the customer and verify that "
            "customer's identity using reliable, independent source documents."
        )
        results = RuleBasedExtractor.extract(text)
        # Should not have both 'mandatory' and 'identification' for same text
        texts_seen = {}
        for r in results:
            key = r.text[:80].lower()
            if key in texts_seen:
                pytest.fail(
                    f"Duplicate obligation for same text: "
                    f"'{key}' has types [{texts_seen[key]}, {r.obligation_type}]"
                )
            texts_seen[key] = r.obligation_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
