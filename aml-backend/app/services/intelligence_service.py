"""Phase 3: Decision Intelligence Service.

Handles decision capture, case memory, loop instrumentation,
pattern detection (clustering), and outcome dashboard metrics.
"""
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, and_, case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import generate_uuid
from app.models.case import Case, CaseStatus, CaseType, CasePriority
from app.models.entity import Entity, RiskLevel
from app.models.screening import ScreeningResult, MatchStatus
from app.models.transaction import TransactionAlert
from app.models.interaction import Interaction
from app.models.intelligence import (
    DecisionCapture,
    CaseMemoryEntry,
    IntelligenceMetric,
    CaseCluster,
)


# ---------------------------------------------------------------------------
# Text utilities for lightweight TF-IDF similarity
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "of", "in", "to", "for",
    "with", "on", "at", "by", "from", "as", "into", "through", "and",
    "but", "or", "nor", "not", "so", "yet", "this", "that", "these",
    "those", "it", "its", "no", "all", "any", "each", "every",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase tokenize, remove stop words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _build_tfidf_vector(tokens: list[str], vocab: dict[str, int], idf: dict[str, float]) -> list[float]:
    """Build a TF-IDF vector for the given tokens."""
    tf = Counter(tokens)
    total = len(tokens) or 1
    vec = [0.0] * len(vocab)
    for token, count in tf.items():
        if token in vocab:
            vec[vocab[token]] = (count / total) * idf.get(token, 1.0)
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1e-10
    norm_b = math.sqrt(sum(x * x for x in b)) or 1e-10
    return dot / (norm_a * norm_b)


def _best_resolution_seconds(capture: "DecisionCapture") -> Optional[int]:
    """Return the best available resolution time in seconds.

    Prefers investigation_time + review_time (explicit user-reported breakdown)
    over the computed time_to_decision_seconds (wall-clock from case creation).
    """
    inv = capture.investigation_time_seconds or 0
    rev = capture.review_time_seconds or 0
    if inv or rev:
        return inv + rev
    return capture.time_to_decision_seconds


# ---------------------------------------------------------------------------
# Decision Capture Service
# ---------------------------------------------------------------------------

class DecisionCaptureService:
    @staticmethod
    async def capture_decision(
        db: AsyncSession,
        case_id: str,
        user_id: str,
        decision: str,
        reasoning_text: str,
        user_confidence: float,
        reasoning_categories: Optional[dict] = None,
        investigation_time_seconds: Optional[int] = None,
        review_time_seconds: Optional[int] = None,
        ai_disposition: Optional[str] = None,
    ) -> DecisionCapture:
        """Capture a structured decision for a case."""
        # Load case + entity context
        case_result = await db.execute(select(Case).where(Case.id == case_id))
        case_obj = case_result.scalar_one_or_none()
        if not case_obj:
            raise ValueError("Case not found")

        entity_result = await db.execute(select(Entity).where(Entity.id == case_obj.entity_id))
        entity = entity_result.scalar_one_or_none()

        # Screening and alert counts
        screening_count = (await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.entity_id == case_obj.entity_id,
                ScreeningResult.status == MatchStatus.TRUE_MATCH,
            )
        )).scalar() or 0

        alert_count = (await db.execute(
            select(func.count(TransactionAlert.id)).where(TransactionAlert.case_id == case_id)
        )).scalar() or 0

        # Compute time to decision
        now = datetime.now(timezone.utc)
        created = case_obj.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        time_to_decision = int((now - created).total_seconds()) if created else None

        capture = DecisionCapture(
            id=generate_uuid(),
            case_id=case_id,
            user_id=user_id,
            decision=decision,
            reasoning_text=reasoning_text,
            reasoning_categories=reasoning_categories,
            user_confidence=user_confidence,
            time_to_decision_seconds=time_to_decision,
            investigation_time_seconds=investigation_time_seconds,
            review_time_seconds=review_time_seconds,
            ai_suggestion=case_obj.ai_suggestion,
            ai_suggestion_confidence=case_obj.decision_confidence,
            ai_disposition=ai_disposition,
            case_type=case_obj.case_type.value if case_obj.case_type else None,
            case_priority=case_obj.priority.value if case_obj.priority else None,
            entity_type=entity.entity_type.value if entity and entity.entity_type else None,
            entity_risk_level=entity.risk_level.value if entity and entity.risk_level else None,
            entity_industry=entity.industry if entity else None,
            entity_country=entity.country if entity else None,
            screening_match_count=screening_count,
            alert_count=alert_count,
        )
        db.add(capture)

        # Also record as interaction for the loop system
        interaction = Interaction(
            id=generate_uuid(),
            user_id=user_id,
            interaction_type="decision_capture",
            action=f"decide_{decision}",
            resource_type="case",
            resource_id=case_id,
            decision=decision,
            reasoning=reasoning_text,
            confidence_level=user_confidence,
            time_to_decision_seconds=time_to_decision,
            ai_suggestion_given=case_obj.ai_suggestion,
            ai_suggestion_accepted=ai_disposition == "accepted" if ai_disposition else None,
            ai_suggestion_feedback=ai_disposition,
            extra_data={
                "reasoning_categories": reasoning_categories,
                "investigation_time": investigation_time_seconds,
                "review_time": review_time_seconds,
            },
        )
        db.add(interaction)

        # Update case memory
        await CaseMemoryService.upsert_memory(db, case_id, capture)

        await db.flush()
        return capture

    @staticmethod
    async def get_case_decisions(db: AsyncSession, case_id: str) -> list[DecisionCapture]:
        result = await db.execute(
            select(DecisionCapture)
            .where(DecisionCapture.case_id == case_id)
            .order_by(DecisionCapture.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_recent_decisions(db: AsyncSession, limit: int = 50) -> list[DecisionCapture]:
        result = await db.execute(
            select(DecisionCapture).order_by(DecisionCapture.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Case Memory Service
# ---------------------------------------------------------------------------

class CaseMemoryService:
    @staticmethod
    async def upsert_memory(
        db: AsyncSession,
        case_id: str,
        capture: Optional[DecisionCapture] = None,
    ) -> CaseMemoryEntry:
        """Create or update a case memory entry from the case and its decision."""
        case_result = await db.execute(select(Case).where(Case.id == case_id))
        case_obj = case_result.scalar_one_or_none()
        if not case_obj:
            raise ValueError("Case not found")

        entity_result = await db.execute(select(Entity).where(Entity.id == case_obj.entity_id))
        entity = entity_result.scalar_one_or_none()

        # Build summary text for similarity search
        parts = [
            f"Case {case_obj.case_number}: {case_obj.title}",
            f"Type: {case_obj.case_type.value}" if case_obj.case_type else "",
            f"Priority: {case_obj.priority.value}" if case_obj.priority else "",
        ]
        if entity:
            parts.append(f"Entity: {entity.name} ({entity.entity_type.value})")
            if entity.risk_level:
                parts.append(f"Risk: {entity.risk_level.value}")
            if entity.industry:
                parts.append(f"Industry: {entity.industry}")
        if case_obj.description:
            parts.append(case_obj.description)
        if capture:
            parts.append(f"Decision: {capture.decision}")
            parts.append(f"Reasoning: {capture.reasoning_text}")
        elif case_obj.decision:
            parts.append(f"Decision: {case_obj.decision}")
            if case_obj.decision_reasoning:
                parts.append(f"Reasoning: {case_obj.decision_reasoning}")

        summary = ". ".join(p for p in parts if p)

        # Build tags
        tags = []
        if entity and entity.risk_level and entity.risk_level.value in ("high", "critical"):
            tags.append("high_risk")
        if capture and capture.screening_match_count and capture.screening_match_count > 0:
            tags.append("screening_match")
        if capture and capture.decision == "sar_filed":
            tags.append("sar_filed")
        if capture and capture.decision == "escalate":
            tags.append("escalated")

        # Check if memory already exists
        existing_result = await db.execute(
            select(CaseMemoryEntry).where(CaseMemoryEntry.case_id == case_id)
        )
        memory = existing_result.scalar_one_or_none()

        if memory:
            memory.summary_text = summary
            memory.decision = capture.decision if capture else case_obj.decision
            memory.decision_capture_id = capture.id if capture else memory.decision_capture_id
            memory.tags = tags
        else:
            memory = CaseMemoryEntry(
                id=generate_uuid(),
                case_id=case_id,
                decision_capture_id=capture.id if capture else None,
                summary_text=summary,
                case_type=case_obj.case_type.value if case_obj.case_type else None,
                decision=capture.decision if capture else case_obj.decision,
                entity_type=entity.entity_type.value if entity and entity.entity_type else None,
                risk_level=entity.risk_level.value if entity and entity.risk_level else None,
                industry=entity.industry if entity else None,
                country=entity.country if entity else None,
                tags=tags,
            )
            db.add(memory)

        await db.flush()
        return memory

    @staticmethod
    async def find_similar_cases(
        db: AsyncSession,
        case_id: str,
        limit: int = 5,
    ) -> list[dict]:
        """Find similar past cases using semantic + structured similarity."""
        # Get the target case
        case_result = await db.execute(select(Case).where(Case.id == case_id))
        target_case = case_result.scalar_one_or_none()
        if not target_case:
            return []

        entity_result = await db.execute(select(Entity).where(Entity.id == target_case.entity_id))
        target_entity = entity_result.scalar_one_or_none()

        # Get all memory entries (excluding this case)
        mem_result = await db.execute(
            select(CaseMemoryEntry).where(CaseMemoryEntry.case_id != case_id)
        )
        memories = list(mem_result.scalars().all())
        if not memories:
            return []

        # Build target text
        target_parts = [
            target_case.title or "",
            target_case.description or "",
            target_case.case_type.value if target_case.case_type else "",
        ]
        if target_entity:
            target_parts.extend([
                target_entity.name or "",
                target_entity.entity_type.value if target_entity.entity_type else "",
                target_entity.risk_level.value if target_entity.risk_level else "",
                target_entity.industry or "",
            ])
        target_text = " ".join(target_parts)
        target_tokens = _tokenize(target_text)

        # Build corpus for TF-IDF
        all_docs = [_tokenize(m.summary_text) for m in memories]
        all_docs.append(target_tokens)

        # Build vocabulary
        vocab_set: set[str] = set()
        for doc in all_docs:
            vocab_set.update(doc)
        vocab = {word: i for i, word in enumerate(sorted(vocab_set))}

        # Compute IDF
        doc_count = len(all_docs)
        df: dict[str, int] = defaultdict(int)
        for doc in all_docs:
            for token in set(doc):
                df[token] += 1
        idf = {word: math.log(doc_count / (count + 1)) + 1 for word, count in df.items()}

        # Target vector
        target_vec = _build_tfidf_vector(target_tokens, vocab, idf)

        # Score each memory
        results = []
        for i, memory in enumerate(memories):
            # Semantic similarity (TF-IDF cosine)
            mem_vec = _build_tfidf_vector(all_docs[i], vocab, idf)
            semantic_score = _cosine_similarity(target_vec, mem_vec)

            # Structured similarity
            struct_score = 0.0
            struct_count = 0
            if memory.case_type and target_case.case_type:
                struct_count += 1
                if memory.case_type == target_case.case_type.value:
                    struct_score += 1.0
            if memory.entity_type and target_entity and target_entity.entity_type:
                struct_count += 1
                if memory.entity_type == target_entity.entity_type.value:
                    struct_score += 1.0
            if memory.risk_level and target_entity and target_entity.risk_level:
                struct_count += 1
                if memory.risk_level == target_entity.risk_level.value:
                    struct_score += 1.0
            if memory.industry and target_entity and target_entity.industry:
                struct_count += 1
                if memory.industry == target_entity.industry:
                    struct_score += 1.0
            if memory.country and target_entity and target_entity.country:
                struct_count += 1
                if memory.country == target_entity.country:
                    struct_score += 1.0

            structured_sim = (struct_score / struct_count) if struct_count > 0 else 0.0

            # Hybrid score: 60% semantic + 40% structured
            hybrid_score = 0.6 * semantic_score + 0.4 * structured_sim

            if hybrid_score > 0.15:  # threshold (raised from 0.05 to filter noise)
                # Load case details
                c_result = await db.execute(select(Case).where(Case.id == memory.case_id))
                c = c_result.scalar_one_or_none()
                if not c:
                    continue

                e_result = await db.execute(select(Entity).where(Entity.id == c.entity_id))
                e = e_result.scalar_one_or_none()

                # Get decision capture for richer reasoning
                dc_result = await db.execute(
                    select(DecisionCapture)
                    .where(DecisionCapture.case_id == memory.case_id)
                    .order_by(DecisionCapture.created_at.desc())
                    .limit(1)
                )
                dc = dc_result.scalar_one_or_none()

                results.append({
                    "case_id": c.id,
                    "case_number": c.case_number,
                    "title": c.title,
                    "case_type": c.case_type.value if c.case_type else None,
                    "decision": dc.decision if dc else c.decision,
                    "reasoning": dc.reasoning_text if dc else c.decision_reasoning,
                    "entity_name": e.name if e else None,
                    "risk_level": memory.risk_level,
                    "similarity_score": round(hybrid_score, 3),
                    "similarity_method": "hybrid",
                    "time_to_decision_minutes": c.time_to_decision_minutes,
                    "user_confidence": dc.user_confidence if dc else c.decision_confidence,
                })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]


# ---------------------------------------------------------------------------
# Loop Instrumentation Service (Enhanced)
# ---------------------------------------------------------------------------

class IntelligenceLoopService:
    @staticmethod
    async def compute_decision_loop(db: AsyncSession) -> dict:
        """Decision loop: AI acceptance rate, override rate, disposition breakdown."""
        # Get all decision captures with AI context
        captures_result = await db.execute(
            select(DecisionCapture).where(DecisionCapture.ai_disposition.isnot(None))
        )
        captures = list(captures_result.scalars().all())

        total_with_ai = len(captures)
        dispositions = Counter(c.ai_disposition for c in captures)

        acceptance_rate = (dispositions.get("accepted", 0) / total_with_ai) if total_with_ai > 0 else 0.0
        override_rate = (
            (dispositions.get("edited", 0) + dispositions.get("rejected", 0)) / total_with_ai
        ) if total_with_ai > 0 else 0.0

        return {
            "total_decisions_with_ai": total_with_ai,
            "ai_acceptance_rate": round(acceptance_rate, 3),
            "ai_override_rate": round(override_rate, 3),
            "disposition_breakdown": dict(dispositions),
        }

    @staticmethod
    async def compute_false_positive_loop(db: AsyncSession) -> dict:
        """False positive loop: alert→dismissed ratio, FP trends."""
        total_resolved = (await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.status != MatchStatus.PENDING
            )
        )).scalar() or 0

        false_positives = (await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.status == MatchStatus.FALSE_POSITIVE
            )
        )).scalar() or 0

        total_alerts = (await db.execute(
            select(func.count(TransactionAlert.id))
        )).scalar() or 0

        dismissed_alerts = (await db.execute(
            select(func.count(TransactionAlert.id)).where(
                TransactionAlert.status == "resolved"
            )
        )).scalar() or 0

        fp_rate = round(false_positives / total_resolved, 3) if total_resolved > 0 else 0.0
        dismissed_ratio = round(dismissed_alerts / total_alerts, 3) if total_alerts > 0 else 0.0

        return {
            "false_positive_rate": fp_rate,
            "total_resolved_screenings": total_resolved,
            "false_positives": false_positives,
            "alert_dismissed_ratio": dismissed_ratio,
            "total_alerts": total_alerts,
            "dismissed_alerts": dismissed_alerts,
        }

    @staticmethod
    async def compute_efficiency_loop(db: AsyncSession) -> dict:
        """Efficiency loop: resolution time, per-step breakdown.

        Uses _best_resolution_seconds() which prefers the explicit
        investigation_time + review_time breakdown over wall-clock
        time_to_decision_seconds.
        """
        captures_result = await db.execute(select(DecisionCapture))
        all_captures = list(captures_result.scalars().all())

        # Filter to captures that have *some* timing data
        captures = [c for c in all_captures if _best_resolution_seconds(c)]

        if captures:
            times = [_best_resolution_seconds(c) for c in captures]
            avg_total = round(sum(times) / len(times) / 60, 1) if times else 0.0

            inv_times = [c.investigation_time_seconds for c in captures if c.investigation_time_seconds]
            avg_investigation = round(sum(inv_times) / len(inv_times) / 60, 1) if inv_times else 0.0

            rev_times = [c.review_time_seconds for c in captures if c.review_time_seconds]
            avg_review = round(sum(rev_times) / len(rev_times) / 60, 1) if rev_times else 0.0
        else:
            # Fall back to case-level timing
            cases_result = await db.execute(
                select(Case).where(Case.time_to_decision_minutes.isnot(None))
            )
            cases = list(cases_result.scalars().all())
            times_min = [c.time_to_decision_minutes for c in cases if c.time_to_decision_minutes]
            avg_total = round(sum(times_min) / len(times_min), 1) if times_min else 0.0
            avg_investigation = 0.0
            avg_review = 0.0

        # By case type — also use _best_resolution_seconds
        by_type: dict[str, float] = {}
        type_groups: dict[str, list[int]] = defaultdict(list)
        for c in captures:
            if c.case_type:
                t = _best_resolution_seconds(c)
                if t:
                    type_groups[c.case_type].append(t)
        for ctype, ts in type_groups.items():
            by_type[ctype] = round(sum(ts) / len(ts) / 60, 1)

        return {
            "avg_resolution_minutes": avg_total,
            "avg_investigation_minutes": avg_investigation,
            "avg_review_minutes": avg_review,
            "resolution_by_type": by_type,
            "total_captured_decisions": len(captures),
        }

    @staticmethod
    async def compute_trust_loop(db: AsyncSession) -> dict:
        """Trust loop: reliance on AI suggestions over time."""
        # Count decisions with and without AI
        total_decisions = (await db.execute(
            select(func.count(DecisionCapture.id))
        )).scalar() or 0

        with_ai = (await db.execute(
            select(func.count(DecisionCapture.id)).where(
                DecisionCapture.ai_disposition.isnot(None)
            )
        )).scalar() or 0

        # AI reliance = % of decisions that had AI suggestions
        reliance = round(with_ai / total_decisions, 3) if total_decisions > 0 else 0.0

        # Confidence when following AI vs overriding
        accepted_conf = await db.execute(
            select(func.avg(DecisionCapture.user_confidence)).where(
                DecisionCapture.ai_disposition == "accepted"
            )
        )
        ac = accepted_conf.scalar()

        override_conf = await db.execute(
            select(func.avg(DecisionCapture.user_confidence)).where(
                DecisionCapture.ai_disposition.in_(["edited", "rejected"])
            )
        )
        oc = override_conf.scalar()

        return {
            "ai_reliance_rate": reliance,
            "total_decisions": total_decisions,
            "decisions_with_ai": with_ai,
            "avg_confidence_when_accepting_ai": round(ac, 3) if ac else None,
            "avg_confidence_when_overriding_ai": round(oc, 3) if oc else None,
        }

    @staticmethod
    async def compute_all_loops(db: AsyncSession) -> dict:
        """Compute all four instrumented loops."""
        now = datetime.now(timezone.utc)
        return {
            "decision_loop": await IntelligenceLoopService.compute_decision_loop(db),
            "false_positive_loop": await IntelligenceLoopService.compute_false_positive_loop(db),
            "efficiency_loop": await IntelligenceLoopService.compute_efficiency_loop(db),
            "trust_loop": await IntelligenceLoopService.compute_trust_loop(db),
            "computed_at": now.isoformat(),
        }


# ---------------------------------------------------------------------------
# Pattern Detection Engine (Enhanced)
# ---------------------------------------------------------------------------

class IntelligencePatternService:
    @staticmethod
    async def detect_case_clusters(db: AsyncSession) -> list[CaseCluster]:
        """Cluster cases by type + decision pattern for repeated patterns."""
        clusters = []

        # 1. Cluster by case_type + decision
        captures_result = await db.execute(select(DecisionCapture))
        captures = list(captures_result.scalars().all())

        if not captures:
            return clusters

        # Group by (case_type, decision)
        groups: dict[tuple, list[DecisionCapture]] = defaultdict(list)
        for c in captures:
            key = (c.case_type or "unknown", c.decision)
            groups[key].append(c)

        for (ctype, decision), group in groups.items():
            if len(group) < 2:
                continue

            confidences = [c.user_confidence for c in group]
            times = [c.time_to_decision_seconds for c in group if c.time_to_decision_seconds]

            cluster = CaseCluster(
                id=generate_uuid(),
                cluster_name=f"{ctype} → {decision} ({len(group)} cases)",
                cluster_type="decision_pattern",
                description=f"Pattern: {len(group)} {ctype} cases resolved with '{decision}' decision",
                case_count=len(group),
                case_ids=[c.case_id for c in group],
                dominant_decision=decision,
                avg_confidence=round(sum(confidences) / len(confidences), 3) if confidences else None,
                avg_resolution_seconds=round(sum(times) / len(times)) if times else None,
                pattern_data={
                    "case_type": ctype,
                    "decision": decision,
                    "confidence_range": [round(min(confidences), 2), round(max(confidences), 2)] if confidences else None,
                },
                severity="low" if decision in ("no_action", "approve") else "medium",
            )
            db.add(cluster)
            clusters.append(cluster)

        # 2. False positive clusters: cases dismissed after screening match
        no_action_after_match = [
            c for c in captures
            if c.decision in ("no_action", "approve") and (c.screening_match_count or 0) > 0
        ]
        if len(no_action_after_match) >= 2:
            fp_cluster = CaseCluster(
                id=generate_uuid(),
                cluster_name=f"Frequent false positives ({len(no_action_after_match)} cases)",
                cluster_type="false_positive_cluster",
                description=(
                    f"{len(no_action_after_match)} cases with screening matches were dismissed. "
                    "Review screening rules or thresholds."
                ),
                case_count=len(no_action_after_match),
                case_ids=[c.case_id for c in no_action_after_match],
                dominant_decision="no_action",
                avg_confidence=round(
                    sum(c.user_confidence for c in no_action_after_match) / len(no_action_after_match), 3
                ),
                pattern_data={
                    "total_matches_dismissed": sum(c.screening_match_count or 0 for c in no_action_after_match),
                },
                severity="high",
            )
            db.add(fp_cluster)
            clusters.append(fp_cluster)

        # 3. Risk-level clusters: high-risk entities with consistent decisions
        risk_groups: dict[str, list[DecisionCapture]] = defaultdict(list)
        for c in captures:
            if c.entity_risk_level:
                risk_groups[c.entity_risk_level].append(c)

        for risk_level, group in risk_groups.items():
            if len(group) < 2:
                continue
            decisions = Counter(c.decision for c in group)
            dominant = decisions.most_common(1)[0]

            cluster = CaseCluster(
                id=generate_uuid(),
                cluster_name=f"{risk_level} risk entities ({len(group)} cases)",
                cluster_type="risk_cluster",
                description=f"{len(group)} cases involving {risk_level}-risk entities. "
                           f"Most common decision: {dominant[0]} ({dominant[1]} times).",
                case_count=len(group),
                case_ids=[c.case_id for c in group],
                dominant_decision=dominant[0],
                avg_confidence=round(sum(c.user_confidence for c in group) / len(group), 3),
                pattern_data={
                    "risk_level": risk_level,
                    "decision_distribution": dict(decisions),
                },
                severity="high" if risk_level in ("high", "critical") else "low",
            )
            db.add(cluster)
            clusters.append(cluster)

        await db.flush()
        return clusters

    @staticmethod
    async def get_active_clusters(db: AsyncSession) -> list[CaseCluster]:
        result = await db.execute(
            select(CaseCluster)
            .where(CaseCluster.is_active == True)
            .order_by(CaseCluster.created_at.desc())
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Outcome Dashboard Service
# ---------------------------------------------------------------------------

class OutcomeDashboardService:
    @staticmethod
    async def get_dashboard_data(db: AsyncSession) -> dict:
        """Comprehensive intelligence dashboard data."""

        # --- Decision distribution ---
        captures_result = await db.execute(select(DecisionCapture))
        all_captures = list(captures_result.scalars().all())

        decision_dist = dict(Counter(c.decision for c in all_captures))
        total_decisions = len(all_captures)

        # Decision consistency: how often the same case_type leads to the same decision
        type_decisions: dict[str, list[str]] = defaultdict(list)
        for c in all_captures:
            if c.case_type:
                type_decisions[c.case_type].append(c.decision)

        consistency_scores = []
        for ctype, decisions in type_decisions.items():
            if len(decisions) > 1:
                most_common = Counter(decisions).most_common(1)[0][1]
                consistency_scores.append(most_common / len(decisions))
        decision_consistency = round(
            sum(consistency_scores) / len(consistency_scores), 3
        ) if consistency_scores else 1.0

        # Confidence distribution
        conf_buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
        for c in all_captures:
            if c.user_confidence < 0.2:
                conf_buckets["0.0-0.2"] += 1
            elif c.user_confidence < 0.4:
                conf_buckets["0.2-0.4"] += 1
            elif c.user_confidence < 0.6:
                conf_buckets["0.4-0.6"] += 1
            elif c.user_confidence < 0.8:
                conf_buckets["0.6-0.8"] += 1
            else:
                conf_buckets["0.8-1.0"] += 1

        avg_confidence = round(
            sum(c.user_confidence for c in all_captures) / total_decisions, 3
        ) if total_decisions > 0 else 0.0

        # --- False positive trends ---
        fp_loop = await IntelligenceLoopService.compute_false_positive_loop(db)

        # --- Resolution speed ---
        eff_loop = await IntelligenceLoopService.compute_efficiency_loop(db)

        # Resolution trend (aggregate by decision date — use daily buckets)
        # Use investigation_time + review_time when available; fall back to time_to_decision_seconds
        resolution_trend = []
        if all_captures:
            by_day: dict[str, list[int]] = defaultdict(list)
            for c in all_captures:
                elapsed = _best_resolution_seconds(c)
                if elapsed and c.created_at:
                    day = c.created_at.strftime("%Y-%m-%d") if hasattr(c.created_at, "strftime") else str(c.created_at)[:10]
                    by_day[day].append(elapsed)
            for day in sorted(by_day.keys()):
                times = by_day[day]
                resolution_trend.append({
                    "period": day,
                    "avg_minutes": round(sum(times) / len(times) / 60, 1),
                    "count": len(times),
                })

        # --- AI usage ---
        dec_loop = await IntelligenceLoopService.compute_decision_loop(db)

        # AI suggestion accuracy: when accepted, did it match the final decision?
        accepted_captures = [c for c in all_captures if c.ai_disposition == "accepted"]
        ai_accuracy = 1.0  # if all accepted, they matched by definition
        # When rejected/edited, AI was wrong
        total_ai = len([c for c in all_captures if c.ai_disposition])
        rejected_count = len([c for c in all_captures if c.ai_disposition in ("rejected",)])
        ai_accuracy = round(1.0 - (rejected_count / total_ai), 3) if total_ai > 0 else 0.0

        # --- Pattern summary ---
        clusters_result = await db.execute(
            select(CaseCluster).where(CaseCluster.is_active == True)
        )
        active_clusters = list(clusters_result.scalars().all())

        fp_clusters = [c for c in active_clusters if c.cluster_type == "false_positive_cluster"]
        recurring_fps = sum(c.case_count for c in fp_clusters)

        top_patterns = [
            {
                "name": c.cluster_name,
                "count": c.case_count,
                "severity": c.severity,
                "type": c.cluster_type,
            }
            for c in sorted(active_clusters, key=lambda x: x.case_count, reverse=True)[:5]
        ]

        # --- Loop health ---
        trust_loop = await IntelligenceLoopService.compute_trust_loop(db)

        return {
            "decision_distribution": decision_dist,
            "decision_consistency_score": decision_consistency,
            "avg_confidence": avg_confidence,
            "confidence_distribution": conf_buckets,
            "false_positive_rate": fp_loop["false_positive_rate"],
            "false_positive_trend": [],  # Will be populated from intelligence_metrics history
            "alert_dismissed_ratio": fp_loop["alert_dismissed_ratio"],
            "avg_resolution_minutes": eff_loop["avg_resolution_minutes"],
            "resolution_trend": resolution_trend,
            "resolution_by_type": eff_loop["resolution_by_type"],
            "ai_acceptance_rate": dec_loop["ai_acceptance_rate"],
            "ai_override_rate": dec_loop["ai_override_rate"],
            "ai_disposition_breakdown": dec_loop["disposition_breakdown"],
            "ai_suggestion_accuracy": ai_accuracy,
            "active_clusters": len(active_clusters),
            "top_patterns": top_patterns,
            "recurring_false_positives": recurring_fps,
            "loop_health": {
                "decision_loop": dec_loop,
                "false_positive_loop": fp_loop,
                "efficiency_loop": eff_loop,
                "trust_loop": trust_loop,
            },
        }
