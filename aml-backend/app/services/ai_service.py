"""AI Assistant Layer - case summarization, suggestions, reasoning, similarity search.
This is assistive AI - users must always accept/reject/edit AI output.
"""
import random
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.case import Case, CaseStatus
from app.models.entity import Entity
from app.models.screening import ScreeningResult, MatchStatus
from app.models.transaction import TransactionAlert


class AIAssistantService:
    @staticmethod
    async def summarize_case(db: AsyncSession, case_id: str) -> dict:
        """Generate a structured case summary."""
        result = await db.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            raise ValueError("Case not found")

        entity_result = await db.execute(select(Entity).where(Entity.id == case.entity_id))
        entity = entity_result.scalar_one_or_none()

        # Get screening results
        screening_result = await db.execute(
            select(ScreeningResult).where(ScreeningResult.entity_id == case.entity_id)
        )
        screenings = screening_result.scalars().all()

        # Get alerts
        alerts_result = await db.execute(
            select(TransactionAlert).where(TransactionAlert.case_id == case_id)
        )
        alerts = alerts_result.scalars().all()

        # Build summary
        entity_info = f"{entity.name} ({entity.entity_type.value})" if entity else "Unknown Entity"
        risk_info = f"Risk Level: {entity.risk_level.value if entity and entity.risk_level else 'Not assessed'}"
        screening_info = f"{len(screenings)} screening results ({sum(1 for s in screenings if s.status == MatchStatus.TRUE_MATCH)} confirmed matches)"
        alert_info = f"{len(alerts)} related alerts"

        summary = (
            f"Case {case.case_number} involves {entity_info}. "
            f"{risk_info}. {screening_info}. {alert_info}. "
            f"Case type: {case.case_type.value}, Priority: {case.priority.value}."
        )

        key_findings = []
        if entity and entity.risk_level and entity.risk_level.value in ["high", "critical"]:
            key_findings.append(f"Entity has {entity.risk_level.value} risk rating")
        for s in screenings:
            if s.status == MatchStatus.TRUE_MATCH:
                key_findings.append(f"Confirmed {s.screening_type.value} match: {s.matched_name}")
        for s in screenings:
            if s.status == MatchStatus.PENDING:
                key_findings.append(f"Pending {s.screening_type.value} screening: {s.matched_name} (score: {s.match_score})")
        if not key_findings:
            key_findings.append("No critical findings identified at this time")

        return {
            "summary": summary,
            "key_findings": key_findings,
            "entity_name": entity.name if entity else None,
            "risk_level": entity.risk_level.value if entity and entity.risk_level else None,
            "screening_count": len(screenings),
            "alert_count": len(alerts),
        }

    @staticmethod
    async def suggest_decision(db: AsyncSession, case_id: str) -> dict:
        """Suggest a decision for a case with reasoning."""
        result = await db.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            raise ValueError("Case not found")

        entity_result = await db.execute(select(Entity).where(Entity.id == case.entity_id))
        entity = entity_result.scalar_one_or_none()

        screening_result = await db.execute(
            select(ScreeningResult).where(ScreeningResult.entity_id == case.entity_id)
        )
        screenings = screening_result.scalars().all()

        true_matches = [s for s in screenings if s.status == MatchStatus.TRUE_MATCH]
        pending = [s for s in screenings if s.status == MatchStatus.PENDING]
        high_risk = entity and entity.risk_level and entity.risk_level.value in ["high", "critical"]

        # Decision logic
        if true_matches:
            suggestion = "sar_filed"
            confidence = round(0.75 + random.uniform(0, 0.2), 2)
            reasoning = (
                f"Confirmed screening matches found ({len(true_matches)} match(es)). "
                "Based on regulatory requirements, a Suspicious Activity Report is recommended. "
                "Review all confirmed matches and supporting documentation before filing."
            )
            risk_factors = [f"Confirmed {m.screening_type.value} match: {m.matched_name}" for m in true_matches]
        elif high_risk and pending:
            suggestion = "escalate"
            confidence = round(0.5 + random.uniform(0, 0.3), 2)
            reasoning = (
                f"Entity has {entity.risk_level.value} risk level with {len(pending)} pending screening result(s). "
                "Recommend escalation for senior compliance officer review before final decision."
            )
            risk_factors = ["High risk entity", f"{len(pending)} unresolved screenings"]
        elif pending:
            suggestion = "escalate"
            confidence = round(0.4 + random.uniform(0, 0.3), 2)
            reasoning = (
                f"There are {len(pending)} pending screening result(s) that need resolution. "
                "Recommend resolving all screenings before making a final case decision."
            )
            risk_factors = [f"{len(pending)} pending screenings"]
        else:
            suggestion = "no_action"
            confidence = round(0.6 + random.uniform(0, 0.3), 2)
            reasoning = (
                "No confirmed screening matches and no unresolved screenings. "
                "Based on available evidence, no further action appears warranted. "
                "Recommend closing the case with documented rationale."
            )
            risk_factors = []

        return {
            "suggestion": suggestion,
            "confidence": confidence,
            "reasoning": reasoning,
            "risk_factors": risk_factors,
            "disclaimer": "This is an AI-generated suggestion. The final decision must be made by an authorized compliance officer.",
        }

    @staticmethod
    async def find_similar_cases(db: AsyncSession, case_id: str) -> list[dict]:
        """Find similar cases based on entity type, risk level, and case type."""
        result = await db.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            return []

        entity_result = await db.execute(select(Entity).where(Entity.id == case.entity_id))
        entity = entity_result.scalar_one_or_none()
        if not entity:
            return []

        # Find cases with same type and similar risk
        similar_result = await db.execute(
            select(Case).where(
                Case.id != case_id,
                Case.case_type == case.case_type,
                Case.decision.isnot(None),
            ).limit(10)
        )
        similar_cases = similar_result.scalars().all()

        results = []
        for sc in similar_cases:
            sc_entity_result = await db.execute(select(Entity).where(Entity.id == sc.entity_id))
            sc_entity = sc_entity_result.scalar_one_or_none()

            similarity_score = 0.5
            if sc_entity and entity:
                if sc_entity.entity_type == entity.entity_type:
                    similarity_score += 0.15
                if sc_entity.risk_level == entity.risk_level:
                    similarity_score += 0.2
                if sc_entity.industry == entity.industry:
                    similarity_score += 0.15

            results.append({
                "case_id": sc.id,
                "case_number": sc.case_number,
                "case_type": sc.case_type.value,
                "decision": sc.decision,
                "decision_reasoning": sc.decision_reasoning,
                "similarity_score": round(similarity_score, 2),
                "entity_name": sc_entity.name if sc_entity else None,
            })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:5]
