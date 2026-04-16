import random
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entity import Entity
from app.models.screening import ScreeningResult, ScreeningType, MatchStatus
from app.models.base import generate_uuid

# Simulated sanctions and PEP lists for demo
SANCTIONS_LIST = [
    {"name": "Ahmad Al-Terroristi", "source": "UN Security Council", "list_id": "UN-SC-2024-001"},
    {"name": "Mohamed Bin Laden", "source": "OFAC SDN", "list_id": "OFAC-SDN-2024-112"},
    {"name": "Khalid Al-Rashid", "source": "EU Sanctions", "list_id": "EU-2024-089"},
    {"name": "Fatima Al-Zahrani", "source": "SAMA Sanctions", "list_id": "SAMA-2024-045"},
    {"name": "Omar Trading Corp", "source": "UN Security Council", "list_id": "UN-SC-2024-033"},
    {"name": "Desert Hawk Industries", "source": "OFAC SDN", "list_id": "OFAC-SDN-2024-200"},
]

PEP_LIST = [
    {"name": "Abdullah Al-Saud", "position": "Government Minister", "country": "SA"},
    {"name": "Mohammed Al-Faisal", "position": "Central Bank Governor", "country": "SA"},
    {"name": "Nora Al-Rashid", "position": "Parliament Member", "country": "SA"},
    {"name": "Salman Trading Group", "position": "State-Owned Enterprise", "country": "SA"},
    {"name": "Ahmed Al-Dosari", "position": "Military General", "country": "SA"},
]


def fuzzy_match_score(name1: str, name2: str) -> float:
    """Simple fuzzy matching based on token overlap."""
    tokens1 = set(name1.lower().split())
    tokens2 = set(name2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard = len(intersection) / len(union)
    # Boost partial matches
    partial_matches = 0
    for t1 in tokens1:
        for t2 in tokens2:
            if t1 in t2 or t2 in t1:
                partial_matches += 1
    partial_boost = min(partial_matches * 0.1, 0.3)
    return min(jaccard + partial_boost, 1.0)


class ScreeningService:
    @staticmethod
    async def screen_entity(
        db: AsyncSession,
        entity_id: str,
        screening_types: list[str],
    ) -> list[ScreeningResult]:
        result = await db.execute(select(Entity).where(Entity.id == entity_id))
        entity = result.scalar_one_or_none()
        if not entity:
            raise ValueError("Entity not found")

        results = []
        entity_name = entity.name

        if "sanctions" in screening_types:
            for entry in SANCTIONS_LIST:
                score = fuzzy_match_score(entity_name, entry["name"])
                if score >= 0.2:
                    ai_sugg, ai_conf, ai_reason = ScreeningService._generate_ai_suggestion(score, "sanctions")
                    sr = ScreeningResult(
                        id=generate_uuid(),
                        entity_id=entity_id,
                        screening_type=ScreeningType.SANCTIONS,
                        matched_name=entry["name"],
                        match_score=round(score, 3),
                        match_source=entry["source"],
                        match_details={"list_id": entry.get("list_id")},
                        status=MatchStatus.PENDING,
                        ai_suggestion=ai_sugg,
                        ai_confidence=ai_conf,
                        ai_reasoning=ai_reason,
                    )
                    db.add(sr)
                    results.append(sr)

        if "pep" in screening_types:
            for entry in PEP_LIST:
                score = fuzzy_match_score(entity_name, entry["name"])
                if score >= 0.2:
                    ai_sugg, ai_conf, ai_reason = ScreeningService._generate_ai_suggestion(score, "pep")
                    sr = ScreeningResult(
                        id=generate_uuid(),
                        entity_id=entity_id,
                        screening_type=ScreeningType.PEP,
                        matched_name=entry["name"],
                        match_score=round(score, 3),
                        match_source="PEP Database",
                        match_details={"position": entry.get("position"), "country": entry.get("country")},
                        status=MatchStatus.PENDING,
                        ai_suggestion=ai_sugg,
                        ai_confidence=ai_conf,
                        ai_reasoning=ai_reason,
                    )
                    db.add(sr)
                    results.append(sr)

        await db.flush()
        return results

    @staticmethod
    def _generate_ai_suggestion(match_score: float, screening_type: str):
        """Generate AI suggestion based on match score."""
        if match_score >= 0.8:
            suggestion = "true_match"
            confidence = round(0.7 + random.uniform(0, 0.25), 2)
            reasoning = (
                f"High name similarity ({match_score:.0%}) suggests a likely {screening_type} match. "
                "Recommend manual verification of identity documents."
            )
        elif match_score >= 0.5:
            suggestion = "inconclusive"
            confidence = round(0.4 + random.uniform(0, 0.3), 2)
            reasoning = (
                f"Moderate name similarity ({match_score:.0%}). "
                "Additional identifiers needed (date of birth, national ID) to confirm or dismiss."
            )
        else:
            suggestion = "false_positive"
            confidence = round(0.6 + random.uniform(0, 0.3), 2)
            reasoning = (
                f"Low name similarity ({match_score:.0%}). "
                "Common name overlap likely. Recommend dismissal unless other risk indicators present."
            )
        return suggestion, confidence, reasoning
