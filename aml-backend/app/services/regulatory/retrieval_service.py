"""Hybrid Retrieval Service — lexical + semantic + structured retrieval.

Combines three retrieval strategies:
1. Lexical: keyword/token matching on provision text, source titles, topic names
2. Semantic: TF-IDF cosine similarity (lightweight, no external embedding service)
3. Structured: graph traversal via DB relationships (source→provision→obligation, topic→source)

Each strategy returns scored results that are fused using reciprocal rank fusion (RRF).

Hardened with:
- Priority 2: Regulator-aware retrieval boost (query-parsed regulator/jurisdiction signals)
- Priority 3: Multi-component confidence scoring (weighted, 0–1 range, better distributed)
"""
import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.regulatory.source import (
    Source, Provision, Topic, Regulator, Jurisdiction, SourceTopic,
    RegulatoryDocument,
)
from app.models.regulatory.obligation import Obligation

logger = logging.getLogger(__name__)

# ── Regulator detection map (P2) ────────────────────────────────────
# Maps query tokens/phrases to known regulator abbreviations + jurisdiction hints.
REGULATOR_ALIASES: dict[str, tuple[str, str]] = {
    # (alias_lowercase) → (regulator_abbreviation, jurisdiction_code)
    "sama": ("SAMA", "SA"),
    "saudi central bank": ("SAMA", "SA"),
    "safiu": ("SAFIU", "SA"),
    "saudi financial intelligence": ("SAFIU", "SA"),
    "cma": ("CMA", "SA"),
    "capital market authority": ("CMA", "SA"),
    "insurance authority": ("IA", "SA"),
    "fatf": ("FATF", "INTL"),
    "financial action task force": ("FATF", "INTL"),
}

# Saudi-specific keywords that imply jurisdiction = SA
SAUDI_KEYWORDS = {
    "saudi", "ksa", "kingdom", "riyal", "sar", "sama", "safiu", "cma",
    "crowdfunding platform", "saudi aml",
}


def _detect_query_regulator(query: str) -> tuple[Optional[str], Optional[str]]:
    """Parse query for regulator mentions and jurisdiction signals.

    Returns (regulator_abbreviation, jurisdiction_code) or (None, None).
    """
    q_lower = query.lower()

    # Check multi-word aliases first (longest match)
    for alias, (abbr, jur) in sorted(REGULATOR_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in q_lower:
            return abbr, jur

    # Check if query implies Saudi jurisdiction even without regulator name
    if any(kw in q_lower for kw in SAUDI_KEYWORDS):
        return None, "SA"

    return None, None


@dataclass
class Citation:
    """A single cited source for an answer."""
    source_id: str
    source_title: str
    source_title_ar: Optional[str] = None
    source_url: Optional[str] = None
    regulator_name: str = ""
    regulator_name_ar: Optional[str] = None
    regulator_abbreviation: str = ""
    jurisdiction_name: str = ""
    jurisdiction_code: str = ""
    authority_level: str = "tier_1"
    is_binding: bool = True
    provision_id: Optional[str] = None
    provision_section: Optional[str] = None
    provision_title: Optional[str] = None
    provision_text: Optional[str] = None
    provision_text_ar: Optional[str] = None
    relevance_score: float = 0.0
    retrieval_method: str = "lexical"


@dataclass
class RetrievalResult:
    """Result from the hybrid retrieval pipeline."""
    query: str
    citations: list[Citation] = field(default_factory=list)
    topics_matched: list[str] = field(default_factory=list)
    answer_text: str = ""
    answer_text_ar: str = ""
    confidence: float = 0.0
    total_results: int = 0
    retrieval_methods_used: list[str] = field(default_factory=list)
    gaps_detected: list[str] = field(default_factory=list)


def _tokenize(text: str) -> set[str]:
    """Simple tokenizer: lowercase, remove punctuation, split on whitespace."""
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return {w for w in text.split() if len(w) > 2}


def _compute_idf(documents: list[set[str]]) -> dict[str, float]:
    """Compute inverse document frequency for a set of tokenized documents."""
    n = len(documents)
    if n == 0:
        return {}
    df: dict[str, int] = defaultdict(int)
    for doc_tokens in documents:
        for token in doc_tokens:
            df[token] += 1
    return {token: math.log((n + 1) / (count + 1)) + 1 for token, count in df.items()}


def _tfidf_score(query_tokens: set[str], doc_tokens: set[str], idf: dict[str, float]) -> float:
    """Compute TF-IDF cosine similarity between query and document."""
    if not query_tokens or not doc_tokens:
        return 0.0
    common = query_tokens & doc_tokens
    if not common:
        return 0.0

    # Query vector
    q_vec = {t: idf.get(t, 1.0) for t in query_tokens}
    q_norm = math.sqrt(sum(v ** 2 for v in q_vec.values()))

    # Doc vector (TF * IDF)
    doc_tf: dict[str, int] = defaultdict(int)
    for t in doc_tokens:
        doc_tf[t] += 1
    d_vec = {t: doc_tf[t] * idf.get(t, 1.0) for t in doc_tokens}
    d_norm = math.sqrt(sum(v ** 2 for v in d_vec.values()))

    if q_norm == 0 or d_norm == 0:
        return 0.0

    dot = sum(q_vec.get(t, 0) * d_vec.get(t, 0) for t in common)
    return dot / (q_norm * d_norm)


def _rrf_fuse(ranked_lists: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion to combine multiple ranked result lists.

    Each input is a list of (provision_id, score) sorted by descending score.
    Returns a fused list sorted by combined RRF score.
    """
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, (pid, _score) in enumerate(ranked):
            scores[pid] += 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _compute_confidence(
    citations: list["Citation"],
    retrieval_methods_used: list[str],
    query_regulator: Optional[str],
    query_jurisdiction: Optional[str],
) -> float:
    """Compute a weighted, interpretable confidence score in 0–1 range.

    Components (P3):
    - retrieval_relevance (0.30): normalized top-N RRF score spread
    - method_coverage   (0.15): how many retrieval strategies contributed
    - regulator_match   (0.20): does the top result match query regulator?
    - jurisdiction_match(0.15): does the top result match query jurisdiction?
    - authority_fit     (0.10): proportion of binding (tier_1) sources
    - answer_support    (0.10): how many citations support the answer
    """
    if not citations:
        return 0.0

    weights = {
        "retrieval_relevance": 0.30,
        "method_coverage": 0.15,
        "regulator_match": 0.20,
        "jurisdiction_match": 0.15,
        "authority_fit": 0.10,
        "answer_support": 0.10,
    }

    scores: dict[str, float] = {}

    # 1. Retrieval relevance — normalize RRF scores to 0–1
    rrf_scores = [c.relevance_score for c in citations]
    max_rrf = max(rrf_scores) if rrf_scores else 0.001
    # Scale: map the best possible RRF score to ~1.0
    # A provision ranked #1 in 3 lists: 3 * 1/(60+1) ≈ 0.049
    # With regulator boost multiplier (up to 3x), max becomes ~0.148
    base_theoretical_max = 3.0 / 61.0  # ~0.049 for k=60 with 3 lists
    # If regulator boost was applied, scores may be multiplied up to 3x
    boost_factor = 3.0 if query_regulator else (1.5 if query_jurisdiction else 1.0)
    theoretical_max = base_theoretical_max * boost_factor
    norm_top = min(max_rrf / theoretical_max, 1.0)
    scores["retrieval_relevance"] = norm_top

    # 2. Method coverage — 1 method = 0.33, 2 = 0.67, 3 = 1.0
    scores["method_coverage"] = min(len(retrieval_methods_used) / 3.0, 1.0)

    # 3. Regulator match — does top citation's regulator match query intent?
    if query_regulator:
        top_reg = citations[0].regulator_abbreviation
        if top_reg == query_regulator:
            scores["regulator_match"] = 1.0
        elif any(c.regulator_abbreviation == query_regulator for c in citations[:3]):
            scores["regulator_match"] = 0.6
        else:
            scores["regulator_match"] = 0.2
    else:
        # No regulator signal → neutral (give partial credit)
        scores["regulator_match"] = 0.5

    # 4. Jurisdiction match
    if query_jurisdiction:
        top_jur = citations[0].jurisdiction_code
        if top_jur == query_jurisdiction:
            scores["jurisdiction_match"] = 1.0
        elif any(c.jurisdiction_code == query_jurisdiction for c in citations[:3]):
            scores["jurisdiction_match"] = 0.6
        else:
            scores["jurisdiction_match"] = 0.2
    else:
        scores["jurisdiction_match"] = 0.5

    # 5. Authority fit — proportion of binding sources
    binding_count = sum(1 for c in citations if c.is_binding)
    scores["authority_fit"] = binding_count / len(citations)

    # 6. Answer support — how many results, scaled to cap at 5
    scores["answer_support"] = min(len(citations) / 5.0, 1.0)

    # Weighted sum
    confidence = sum(weights[k] * scores[k] for k in weights)
    return round(min(max(confidence, 0.0), 1.0), 2)


class HybridRetrievalService:
    """Orchestrates multi-strategy retrieval across the regulatory knowledge base."""

    @staticmethod
    async def search(
        db: AsyncSession,
        query: str,
        topic_filter: Optional[str] = None,
        regulator_filter: Optional[str] = None,
        jurisdiction_filter: Optional[str] = None,
        authority_level_filter: Optional[str] = None,
        limit: int = 10,
    ) -> RetrievalResult:
        """Run hybrid retrieval and return cited results.

        P2: Detects regulator mentions in the query and applies a boost
            so regulator-specific queries rank the named regulator first.
        P3: Uses weighted multi-component confidence scoring.
        """
        result = RetrievalResult(query=query)
        query_tokens = _tokenize(query)

        if not query_tokens:
            return result

        # --- P2: Detect regulator / jurisdiction intent from query ---
        query_regulator, query_jurisdiction = _detect_query_regulator(query)

        # --- Load provisions with full context ---
        prov_query = (
            select(Provision)
            .join(RegulatoryDocument, Provision.document_id == RegulatoryDocument.id)
            .join(Regulator, RegulatoryDocument.regulator_id == Regulator.id)
            .join(Jurisdiction, RegulatoryDocument.jurisdiction_id == Jurisdiction.id)
        )

        if regulator_filter:
            prov_query = prov_query.where(Regulator.abbreviation == regulator_filter)
        if jurisdiction_filter:
            prov_query = prov_query.where(Jurisdiction.code == jurisdiction_filter)

        prov_result = await db.execute(prov_query)
        provisions = list(prov_result.scalars().all())

        if not provisions:
            result.gaps_detected.append("No provisions found in the knowledge base")
            return result

        # --- Pre-load provision→regulator mapping for P2 boost ---
        prov_regulator_map: dict[str, str] = {}  # provision_id → regulator_abbreviation
        prov_jurisdiction_map: dict[str, str] = {}  # provision_id → jurisdiction_code
        for prov in provisions:
            doc = await db.get(RegulatoryDocument, prov.document_id)
            if doc:
                reg = await db.get(Regulator, doc.regulator_id)
                jur = await db.get(Jurisdiction, doc.jurisdiction_id)
                if reg:
                    prov_regulator_map[prov.id] = reg.abbreviation
                if jur:
                    prov_jurisdiction_map[prov.id] = jur.code

        # --- Strategy 1: Lexical (keyword match) ---
        lexical_ranked: list[tuple[str, float]] = []
        prov_tokens_map: dict[str, set[str]] = {}
        for prov in provisions:
            text_combined = f"{prov.title or ''} {prov.text} {prov.text_ar or ''}"
            prov_tokens = _tokenize(text_combined)
            prov_tokens_map[prov.id] = prov_tokens
            overlap = len(query_tokens & prov_tokens)
            if overlap > 0:
                score = overlap / max(len(query_tokens), 1)
                lexical_ranked.append((prov.id, score))

        lexical_ranked.sort(key=lambda x: x[1], reverse=True)
        if lexical_ranked:
            result.retrieval_methods_used.append("lexical")

        # --- Strategy 2: Semantic (TF-IDF cosine) ---
        all_doc_tokens = list(prov_tokens_map.values())
        idf = _compute_idf(all_doc_tokens)

        semantic_ranked: list[tuple[str, float]] = []
        for prov_id, doc_tokens in prov_tokens_map.items():
            score = _tfidf_score(query_tokens, doc_tokens, idf)
            if score > 0:
                semantic_ranked.append((prov_id, score))

        semantic_ranked.sort(key=lambda x: x[1], reverse=True)
        if semantic_ranked:
            result.retrieval_methods_used.append("semantic")

        # --- Strategy 3: Structured (topic-based graph traversal) ---
        structured_ranked: list[tuple[str, float]] = []

        # Find matching topics
        topic_result = await db.execute(select(Topic))
        all_topics = list(topic_result.scalars().all())
        matched_topics: list[Topic] = []
        for topic in all_topics:
            topic_tokens = _tokenize(f"{topic.name} {topic.name_ar or ''} {topic.category}")
            if query_tokens & topic_tokens:
                matched_topics.append(topic)
                result.topics_matched.append(topic.name)

        if matched_topics:
            # Find sources linked to matched topics
            topic_ids = [t.id for t in matched_topics]
            st_result = await db.execute(
                select(SourceTopic).where(SourceTopic.topic_id.in_(topic_ids))
            )
            source_topic_links = list(st_result.scalars().all())
            source_ids = list({st.source_id for st in source_topic_links})

            if source_ids:
                source_result = await db.execute(
                    select(Source).where(Source.id.in_(source_ids))
                )
                sources = list(source_result.scalars().all())
                regulator_ids = list({s.regulator_id for s in sources})

                doc_result = await db.execute(
                    select(RegulatoryDocument).where(
                        RegulatoryDocument.regulator_id.in_(regulator_ids)
                    )
                )
                doc_ids = [d.id for d in doc_result.scalars().all()]

                topic_prov_ids = set()
                for prov in provisions:
                    if prov.document_id in doc_ids:
                        topic_prov_ids.add(prov.id)
                        score = len([st for st in source_topic_links
                                    if st.source_id in source_ids]) / max(len(topic_ids), 1)
                        structured_ranked.append((prov.id, min(score, 1.0)))

            structured_ranked.sort(key=lambda x: x[1], reverse=True)
            if structured_ranked:
                result.retrieval_methods_used.append("structured")

        # --- Fuse base results with RRF ---
        ranked_lists = [r for r in [
            lexical_ranked, semantic_ranked, structured_ranked
        ] if r]
        if not ranked_lists:
            result.gaps_detected.append(f"No relevant provisions found for query: {query}")
            return result

        fused = _rrf_fuse(ranked_lists)

        # --- P2: Regulator-aware post-RRF re-ranking ---
        # Apply a multiplicative boost to fused scores so that provisions
        # from the query-mentioned regulator float to the top.
        if query_regulator or query_jurisdiction:
            boosted: list[tuple[str, float]] = []
            for pid, score in fused:
                multiplier = 1.0
                prov_reg = prov_regulator_map.get(pid, "")
                prov_jur = prov_jurisdiction_map.get(pid, "")

                if query_regulator and prov_reg == query_regulator:
                    multiplier += 1.5  # strong boost for exact regulator match
                if query_jurisdiction and prov_jur == query_jurisdiction:
                    multiplier += 0.5  # moderate boost for jurisdiction match

                boosted.append((pid, score * multiplier))

            fused = sorted(boosted, key=lambda x: x[1], reverse=True)
            result.retrieval_methods_used.append("regulator_boost")

        top_prov_ids = [pid for pid, _score in fused[:limit]]

        # --- Build citations with full provenance ---
        prov_map = {p.id: p for p in provisions}
        fused_scores = {pid: score for pid, score in fused}

        for prov_id in top_prov_ids:
            prov = prov_map.get(prov_id)
            if not prov:
                continue

            doc = await db.get(RegulatoryDocument, prov.document_id)
            if not doc:
                continue

            regulator = await db.get(Regulator, doc.regulator_id)
            jurisdiction = await db.get(Jurisdiction, doc.jurisdiction_id)

            src_result = await db.execute(
                select(Source).where(Source.regulator_id == doc.regulator_id).limit(1)
            )
            source = src_result.scalar_one_or_none()

            authority_level = source.authority_level if source else "tier_1"
            if hasattr(authority_level, 'value'):
                authority_level = authority_level.value

            is_binding = authority_level in ("tier_1", "TIER_1")

            if authority_level_filter and authority_level != authority_level_filter:
                continue

            citation = Citation(
                source_id=source.id if source else "",
                source_title=source.title if source else doc.title,
                source_title_ar=source.title_ar if source else doc.title_ar,
                source_url=source.url if source else None,
                regulator_name=regulator.name if regulator else "",
                regulator_name_ar=regulator.name_ar if regulator else None,
                regulator_abbreviation=regulator.abbreviation if regulator else "",
                jurisdiction_name=jurisdiction.name if jurisdiction else "",
                jurisdiction_code=jurisdiction.code if jurisdiction else "",
                authority_level=authority_level,
                is_binding=is_binding,
                provision_id=prov.id,
                provision_section=prov.section_number,
                provision_title=prov.title,
                provision_text=prov.text,
                provision_text_ar=prov.text_ar,
                relevance_score=round(fused_scores.get(prov_id, 0.0), 4),
                retrieval_method=", ".join(result.retrieval_methods_used),
            )
            result.citations.append(citation)

        result.total_results = len(result.citations)

        # --- P3: Weighted multi-component confidence ---
        if result.citations:
            result.confidence = _compute_confidence(
                result.citations,
                result.retrieval_methods_used,
                query_regulator,
                query_jurisdiction,
            )
        else:
            result.gaps_detected.append(f"Query returned no matching provisions: {query}")

        # Generate answer summary
        if result.citations:
            top = result.citations[0]
            binding_label = "binding" if top.is_binding else "non-binding"
            result.answer_text = (
                f"Based on {len(result.citations)} relevant provision(s) from "
                f"{len(set(c.regulator_abbreviation for c in result.citations))} regulator(s). "
                f"The most relevant provision is from {top.regulator_abbreviation} "
                f"({top.authority_level}, {binding_label}): "
                f"{top.provision_title or 'N/A'} — {(top.provision_text or '')[:300]}"
            )
            result.answer_text_ar = (
                f"استناداً إلى {len(result.citations)} حكم/أحكام ذات صلة من "
                f"{len(set(c.regulator_abbreviation for c in result.citations))} جهة/جهات تنظيمية."
            )

        return result

    @staticmethod
    async def ask(
        db: AsyncSession,
        query: str,
        topic_filter: Optional[str] = None,
        regulator_filter: Optional[str] = None,
        jurisdiction_filter: Optional[str] = None,
        authority_level_filter: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        """High-level ask endpoint that returns a structured response with citations.

        Returns a dict suitable for JSON serialization with all required fields:
        source title, URL, regulator, jurisdiction, authority tier, binding status,
        confidence, and provision citations.
        """
        retrieval = await HybridRetrievalService.search(
            db, query, topic_filter, regulator_filter,
            jurisdiction_filter, authority_level_filter, limit,
        )

        # Log the query
        from app.models.regulatory.change import QueryLog
        query_log = QueryLog(
            query_text=query,
            response_text=retrieval.answer_text,
            response_confidence=retrieval.confidence,
            sources_used=[c.source_id for c in retrieval.citations],
            gaps_detected=retrieval.gaps_detected if retrieval.gaps_detected else None,
        )
        db.add(query_log)

        citations_out = []
        for c in retrieval.citations:
            citations_out.append({
                "source_title": c.source_title,
                "source_title_ar": c.source_title_ar,
                "source_url": c.source_url,
                "regulator": c.regulator_name,
                "regulator_ar": c.regulator_name_ar,
                "regulator_abbreviation": c.regulator_abbreviation,
                "jurisdiction": c.jurisdiction_name,
                "jurisdiction_code": c.jurisdiction_code,
                "authority_level": c.authority_level,
                "is_binding": c.is_binding,
                "binding_status": "Binding" if c.is_binding else "Non-binding",
                "provision_id": c.provision_id,
                "provision_section": c.provision_section,
                "provision_title": c.provision_title,
                "provision_text": c.provision_text,
                "provision_text_ar": c.provision_text_ar,
                "relevance_score": c.relevance_score,
                "retrieval_method": c.retrieval_method,
            })

        return {
            "query": retrieval.query,
            "answer": retrieval.answer_text,
            "answer_ar": retrieval.answer_text_ar,
            "confidence": retrieval.confidence,
            "total_results": retrieval.total_results,
            "topics_matched": retrieval.topics_matched,
            "retrieval_methods_used": retrieval.retrieval_methods_used,
            "citations": citations_out,
            "gaps_detected": retrieval.gaps_detected,
            "disclaimer": "This information is for compliance reference only. "
                         "Always verify against the original regulatory source.",
            "disclaimer_ar": "هذه المعلومات للاسترشاد فقط. يرجى التحقق دائماً من المصدر التنظيمي الأصلي.",
        }
