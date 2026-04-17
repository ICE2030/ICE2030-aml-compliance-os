"""Hybrid Retrieval Service — lexical + semantic + structured retrieval.

Combines three retrieval strategies:
1. Lexical: keyword/token matching on provision text, source titles, topic names
2. Semantic: TF-IDF cosine similarity (lightweight, no external embedding service)
3. Structured: graph traversal via DB relationships (source→provision→obligation, topic→source)

Each strategy returns scored results that are fused using reciprocal rank fusion (RRF).
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
        """Run hybrid retrieval and return cited results."""
        result = RetrievalResult(query=query)
        query_tokens = _tokenize(query)

        if not query_tokens:
            return result

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
                # Find provisions from documents linked to those sources' regulators
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

                # Score provisions from topic-linked sources higher
                topic_prov_ids = set()
                for prov in provisions:
                    if prov.document_id in doc_ids:
                        topic_prov_ids.add(prov.id)
                        # Score based on number of matching topics
                        score = len([st for st in source_topic_links
                                    if st.source_id in source_ids]) / max(len(topic_ids), 1)
                        structured_ranked.append((prov.id, min(score, 1.0)))

            structured_ranked.sort(key=lambda x: x[1], reverse=True)
            if structured_ranked:
                result.retrieval_methods_used.append("structured")

        # --- Fuse results with RRF ---
        ranked_lists = [r for r in [lexical_ranked, semantic_ranked, structured_ranked] if r]
        if not ranked_lists:
            result.gaps_detected.append(f"No relevant provisions found for query: {query}")
            return result

        fused = _rrf_fuse(ranked_lists)
        top_prov_ids = [pid for pid, _score in fused[:limit]]

        # --- Build citations with full provenance ---
        prov_map = {p.id: p for p in provisions}
        fused_scores = {pid: score for pid, score in fused}

        # Load related source/regulator/jurisdiction data
        for prov_id in top_prov_ids:
            prov = prov_map.get(prov_id)
            if not prov:
                continue

            # Load the document's regulator and jurisdiction
            doc = await db.get(RegulatoryDocument, prov.document_id)
            if not doc:
                continue

            regulator = await db.get(Regulator, doc.regulator_id)
            jurisdiction = await db.get(Jurisdiction, doc.jurisdiction_id)

            # Find the source for this document's regulator
            src_result = await db.execute(
                select(Source).where(Source.regulator_id == doc.regulator_id).limit(1)
            )
            source = src_result.scalar_one_or_none()

            authority_level = source.authority_level if source else "tier_1"
            # Convert enum to string if needed
            if hasattr(authority_level, 'value'):
                authority_level = authority_level.value

            is_binding = authority_level in ("tier_1", "TIER_1")

            # Apply authority filter if specified
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

        # Compute overall confidence based on top scores and coverage
        if result.citations:
            avg_score = sum(c.relevance_score for c in result.citations) / len(result.citations)
            method_bonus = len(result.retrieval_methods_used) * 0.1
            result.confidence = min(round(avg_score + method_bonus, 2), 1.0)
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
