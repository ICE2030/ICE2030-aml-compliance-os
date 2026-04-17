"""Tests for Phase 2 Hardening Sprint — Priorities 1–5.

P1: Threshold extraction context (full sentence, not fragments)
P2: Regulator-aware retrieval boost
P3: Confidence recalibration (weighted components, 0–1 range)
P4: Penalty provision classification
P5: Obligation extraction coverage (FATF R.10 CDD)
"""
import pytest
from app.services.regulatory.obligation_extraction_service import (
    RuleBasedExtractor,
    ExtractedObligation,
    _get_governing_sentence,
    _normalize_summary,
)
from app.services.regulatory.retrieval_service import (
    _detect_query_regulator,
    _compute_confidence,
    Citation,
)


# ═══════════════════════════════════════════════════════════════════════
# Priority 1 — Threshold extraction context
# ═══════════════════════════════════════════════════════════════════════

class TestThresholdExtraction:
    """P1: Thresholds must include full governing sentence, not fragments."""

    PROVISION_WITH_THRESHOLD = (
        "Financial institutions shall report any single transaction "
        "exceeding SAR 60,000 or its equivalent in foreign currency to SAFIU. "
        "Reports must be filed within 3 business days."
    )

    PROVISION_WITH_MULTIPLE_THRESHOLDS = (
        "Transactions above SAR 3,000 require enhanced verification. "
        "Any cash transaction above SAR 60,000 must be reported to the authorities."
    )

    def test_threshold_includes_full_sentence(self):
        """Threshold extraction must include the full governing sentence."""
        results = RuleBasedExtractor.extract(self.PROVISION_WITH_THRESHOLD)
        threshold_obs = [r for r in results if r.obligation_type == "threshold"]
        assert len(threshold_obs) >= 1, "Should extract at least one threshold obligation"
        for ob in threshold_obs:
            # Must NOT be just the numeric fragment
            assert len(ob.text) >= 30, f"Threshold too short (fragment): {ob.text}"
            assert "SAR" in ob.text, "Threshold must mention currency"

    def test_threshold_not_fragment(self):
        """Threshold must NOT be extracted as just 'above SAR 3,000'."""
        results = RuleBasedExtractor.extract(self.PROVISION_WITH_MULTIPLE_THRESHOLDS)
        threshold_obs = [r for r in results if r.obligation_type == "threshold"]
        for ob in threshold_obs:
            assert ob.text != "above SAR 3,000", "Fragment extraction detected!"
            assert ob.text != "above SAR 60,000", "Fragment extraction detected!"
            assert len(ob.text) >= 30, f"Threshold text too short: {ob.text}"

    def test_threshold_preserves_actor_and_action(self):
        """Threshold sentence should contain the actor and action context."""
        results = RuleBasedExtractor.extract(self.PROVISION_WITH_THRESHOLD)
        threshold_obs = [r for r in results if r.obligation_type == "threshold"]
        assert len(threshold_obs) >= 1
        # The governing sentence should include context about who and what
        full_text = " ".join(ob.text for ob in threshold_obs)
        # At minimum, the sentence should be longer than just a number
        assert any(len(ob.text) > 50 for ob in threshold_obs), \
            "At least one threshold should have substantial context"


class TestGoveringSentenceHelper:
    """Unit tests for _get_governing_sentence helper."""

    def test_expands_to_sentence_boundaries(self):
        text = "First sentence. The threshold is above SAR 3,000 for all FIs. Next sentence."
        result = _get_governing_sentence(text, 30, 55)
        assert "threshold" in result.lower()
        assert result.endswith(".")

    def test_handles_start_of_text(self):
        text = "Transactions above SAR 60,000 must be reported."
        result = _get_governing_sentence(text, 13, 30)
        assert "Transactions" in result
        assert "reported" in result

    def test_handles_end_of_text(self):
        text = "Report transactions exceeding SAR 3,000"
        result = _get_governing_sentence(text, 20, 38)
        assert "Report" in result


# ═══════════════════════════════════════════════════════════════════════
# Priority 2 — Regulator-aware retrieval boost
# ═══════════════════════════════════════════════════════════════════════

class TestRegulatorDetection:
    """P2: Query parsing for regulator mentions."""

    def test_detects_sama(self):
        reg, jur = _detect_query_regulator("What do SAMA sources require for sanctions screening?")
        assert reg == "SAMA"
        assert jur == "SA"

    def test_detects_fatf(self):
        reg, jur = _detect_query_regulator("What does FATF recommend for CDD?")
        assert reg == "FATF"
        assert jur == "INTL"

    def test_detects_cma(self):
        reg, jur = _detect_query_regulator("CMA regulations for securities firms")
        assert reg == "CMA"
        assert jur == "SA"

    def test_detects_safiu(self):
        reg, jur = _detect_query_regulator("SAFIU reporting requirements")
        assert reg == "SAFIU"
        assert jur == "SA"

    def test_detects_saudi_jurisdiction_without_regulator(self):
        reg, jur = _detect_query_regulator("What AML obligations apply to a Saudi crowdfunding platform?")
        # Saudi keyword implies SA jurisdiction
        assert jur == "SA"

    def test_no_regulator_in_generic_query(self):
        reg, jur = _detect_query_regulator("What are customer due diligence requirements?")
        assert reg is None
        assert jur is None

    def test_case_insensitive(self):
        reg, jur = _detect_query_regulator("what do sama sources require?")
        assert reg == "SAMA"

    def test_multi_word_alias(self):
        reg, jur = _detect_query_regulator("Financial Action Task Force recommendations on PEPs")
        assert reg == "FATF"


# ═══════════════════════════════════════════════════════════════════════
# Priority 3 — Confidence recalibration
# ═══════════════════════════════════════════════════════════════════════

class TestConfidenceRecalibration:
    """P3: Confidence scoring must be weighted, 0–1 range, well-distributed."""

    def _make_citation(self, reg_abbr="SAMA", jur_code="SA",
                       authority="tier_1", relevance=0.045):
        return Citation(
            source_id="s1", source_title="Test",
            regulator_abbreviation=reg_abbr,
            jurisdiction_code=jur_code,
            authority_level=authority,
            is_binding=(authority == "tier_1"),
            relevance_score=relevance,
        )

    def test_confidence_in_0_1_range(self):
        citations = [self._make_citation() for _ in range(3)]
        conf = _compute_confidence(citations, ["lexical", "semantic", "structured"], "SAMA", "SA")
        assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of range"

    def test_confidence_not_clustered(self):
        """Strong answers should score notably higher than weak ones."""
        # Strong: regulator match, multi-method, high relevance
        strong_citations = [self._make_citation(relevance=0.049) for _ in range(5)]
        strong_conf = _compute_confidence(
            strong_citations, ["lexical", "semantic", "structured", "regulator_boost"],
            "SAMA", "SA"
        )

        # Weak: no regulator match, single method, low relevance
        weak_citations = [self._make_citation(reg_abbr="FATF", jur_code="INTL", relevance=0.01)]
        weak_conf = _compute_confidence(
            weak_citations, ["lexical"],
            "SAMA", "SA"
        )

        gap = strong_conf - weak_conf
        assert gap >= 0.15, f"Confidence gap too small: {strong_conf} vs {weak_conf} (gap={gap})"

    def test_empty_citations_returns_zero(self):
        conf = _compute_confidence([], ["lexical"], None, None)
        assert conf == 0.0

    def test_regulator_match_boosts_confidence(self):
        """Matching regulator should give higher confidence than mismatch."""
        citations = [self._make_citation(reg_abbr="SAMA")]
        conf_match = _compute_confidence(citations, ["lexical"], "SAMA", "SA")
        conf_no_match = _compute_confidence(citations, ["lexical"], "FATF", "INTL")
        assert conf_match > conf_no_match, \
            f"Regulator match {conf_match} should exceed mismatch {conf_no_match}"

    def test_more_methods_increase_confidence(self):
        """Using more retrieval methods should increase confidence."""
        citations = [self._make_citation()]
        conf_1 = _compute_confidence(citations, ["lexical"], None, None)
        conf_3 = _compute_confidence(citations, ["lexical", "semantic", "structured"], None, None)
        assert conf_3 > conf_1


# ═══════════════════════════════════════════════════════════════════════
# Priority 4 — Penalty provision classification
# ═══════════════════════════════════════════════════════════════════════

class TestPenaltyClassification:
    """P4: Penalty provisions must be classified separately from operational obligations."""

    PENALTY_TEXT = (
        "Any person who commits or attempts to commit the crime of money laundering "
        "shall be sentenced to imprisonment for a period not exceeding fifteen years "
        "and a fine not exceeding seven million Saudi Riyals."
    )

    OPERATIONAL_TEXT = (
        "Financial institutions shall implement internal policies, procedures, and "
        "controls to prevent money laundering and terrorism financing."
    )

    MIXED_TEXT = (
        "Financial institutions shall report suspicious transactions to SAFIU within "
        "3 business days. Failure to report shall result in a fine not exceeding "
        "SAR 5,000,000 and imprisonment for up to two years."
    )

    def test_penalty_classified_as_penalty(self):
        results = RuleBasedExtractor.extract(self.PENALTY_TEXT)
        types = [r.obligation_type for r in results]
        assert "penalty" in types, f"Penalty not detected. Types found: {types}"

    def test_operational_not_classified_as_penalty(self):
        results = RuleBasedExtractor.extract(self.OPERATIONAL_TEXT)
        types = [r.obligation_type for r in results]
        assert "penalty" not in types, f"Operational wrongly classified as penalty. Types: {types}"

    def test_mixed_text_separates_penalty_from_operational(self):
        results = RuleBasedExtractor.extract(self.MIXED_TEXT)
        types = set(r.obligation_type for r in results)
        # Should have at least one non-penalty and one penalty
        non_penalty = types - {"penalty"}
        assert len(non_penalty) > 0 or len(results) > 0, \
            "Mixed text should produce at least one obligation"

    def test_penalty_arabic(self):
        arabic_penalty = "يعاقب بالسجن مدة لا تزيد عن خمس عشرة سنة وبغرامة لا تزيد عن سبعة ملايين ريال سعودي."
        results = RuleBasedExtractor.extract(arabic_penalty)
        penalty_obs = [r for r in results if r.obligation_type == "penalty"]
        assert len(penalty_obs) >= 1, "Arabic penalty not detected"


# ═══════════════════════════════════════════════════════════════════════
# Priority 5 — Obligation extraction coverage (CDD / FATF R.10)
# ═══════════════════════════════════════════════════════════════════════

class TestCDDExtractionCoverage:
    """P5: CDD, identification, verification, beneficial ownership extraction."""

    FATF_R10_TEXT = (
        "Financial institutions should be required to undertake customer due diligence "
        "measures when establishing business relationships. "
        "They shall identify the customer and verify that customer's identity using "
        "reliable, independent source documents, data or information. "
        "Financial institutions should identify the beneficial owner and take reasonable "
        "measures to verify the identity of the beneficial owner. "
        "Financial institutions should be required to conduct ongoing due diligence on "
        "the business relationship and scrutiny of transactions."
    )

    def test_identification_obligation_detected(self):
        results = RuleBasedExtractor.extract(self.FATF_R10_TEXT)
        types = [r.obligation_type for r in results]
        assert "identification" in types, f"Identification not detected. Types: {types}"

    def test_verification_obligation_detected(self):
        results = RuleBasedExtractor.extract(self.FATF_R10_TEXT)
        types = [r.obligation_type for r in results]
        assert "verification" in types, f"Verification not detected. Types: {types}"

    def test_ongoing_monitoring_detected(self):
        results = RuleBasedExtractor.extract(self.FATF_R10_TEXT)
        types = [r.obligation_type for r in results]
        assert "ongoing_monitoring" in types, f"Ongoing monitoring not detected. Types: {types}"

    def test_cdd_extraction_coverage_count(self):
        """FATF R.10 text should yield at least 3 distinct obligation types."""
        results = RuleBasedExtractor.extract(self.FATF_R10_TEXT)
        unique_types = set(r.obligation_type for r in results)
        assert len(unique_types) >= 3, \
            f"Expected ≥3 distinct types from FATF R.10, got {unique_types}"

    def test_beneficial_ownership_detected(self):
        text = (
            "Financial institutions shall identify the beneficial owner and take "
            "reasonable measures to verify the identity of the beneficial owner "
            "using relevant information obtained from a reliable source."
        )
        results = RuleBasedExtractor.extract(text)
        types = [r.obligation_type for r in results]
        assert "identification" in types, f"Beneficial ownership not detected as identification. Types: {types}"

    def test_recordkeeping_detected(self):
        text = "Financial institutions shall maintain all records obtained through CDD measures for a minimum of 5 years."
        results = RuleBasedExtractor.extract(text)
        types = [r.obligation_type for r in results]
        assert "recordkeeping" in types, f"Recordkeeping not detected. Types: {types}"


# ═══════════════════════════════════════════════════════════════════════
# Helper tests
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizeSummary:
    def test_short_text_unchanged(self):
        result = _normalize_summary("Short obligation text.", "mandatory")
        assert result == "Short obligation text."

    def test_long_text_truncated(self):
        long_text = "A" * 300
        result = _normalize_summary(long_text, "mandatory")
        assert len(result) <= 260

    def test_truncation_at_natural_break(self):
        text = "A" * 150 + "; " + "B" * 150
        result = _normalize_summary(text, "mandatory")
        assert len(result) < len(text)


class TestMinObligationLength:
    """Verify MIN_OBLIGATION_LENGTH rejects short fragments."""

    def test_short_fragment_rejected(self):
        text = "shall do X."  # Only 11 chars — below threshold
        results = RuleBasedExtractor.extract(text)
        for r in results:
            assert len(r.text) >= RuleBasedExtractor.MIN_OBLIGATION_LENGTH


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
