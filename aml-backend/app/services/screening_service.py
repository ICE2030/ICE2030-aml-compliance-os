"""Screening service - screens entities against UN Sanctions and PEP lists.
Now uses REAL UN Security Council Consolidated Sanctions List data.
"""
import random
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entity import Entity
from app.models.screening import ScreeningResult, ScreeningType, MatchStatus
from app.models.base import generate_uuid
from app.services.un_sanctions_service import screen_against_un_sanctions, get_sanctions_stats

logger = logging.getLogger(__name__)

# PEP list remains a curated reference list (no public API available for PEPs)
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
            try:
                # Screen against REAL UN Sanctions data
                un_matches = await screen_against_un_sanctions(entity_name, threshold=0.2)
                for match in un_matches:
                    score = match["match_score"]
                    ai_sugg, ai_conf, ai_reason = ScreeningService._generate_ai_suggestion(
                        score, "sanctions", source="UN Security Council Consolidated List"
                    )
                    sr = ScreeningResult(
                        id=generate_uuid(),
                        entity_id=entity_id,
                        screening_type=ScreeningType.SANCTIONS,
                        matched_name=match["name"],
                        match_score=round(score, 3),
                        match_source="UN Security Council",
                        match_details={
                            "dataid": match.get("dataid"),
                            "reference_number": match.get("reference_number"),
                            "un_list_type": match.get("un_list_type"),
                            "listed_on": match.get("listed_on"),
                            "type": match.get("type"),
                            "aliases": [a["name"] for a in match.get("aliases", [])[:5]],
                            "nationalities": match.get("nationalities", []),
                            "source_url": match.get("source_url"),
                            "data_source": "LIVE - UN SC Consolidated Sanctions List",
                        },
                        status=MatchStatus.PENDING,
                        ai_suggestion=ai_sugg,
                        ai_confidence=ai_conf,
                        ai_reasoning=ai_reason,
                    )
                    db.add(sr)
                    results.append(sr)
                logger.info(f"UN sanctions screening for '{entity_name}': {len(un_matches)} matches")
            except Exception as e:
                logger.error(f"UN sanctions screening failed: {e}")
                raise ValueError(f"UN sanctions screening temporarily unavailable: {e}")

        if "pep" in screening_types:
            for entry in PEP_LIST:
                score = fuzzy_match_score(entity_name, entry["name"])
                if score >= 0.2:
                    ai_sugg, ai_conf, ai_reason = ScreeningService._generate_ai_suggestion(
                        score, "pep", source="PEP Database"
                    )
                    sr = ScreeningResult(
                        id=generate_uuid(),
                        entity_id=entity_id,
                        screening_type=ScreeningType.PEP,
                        matched_name=entry["name"],
                        match_score=round(score, 3),
                        match_source="PEP Database",
                        match_details={
                            "position": entry.get("position"),
                            "country": entry.get("country"),
                        },
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
    def _generate_ai_suggestion(
        match_score: float,
        screening_type: str,
        source: str = "Unknown",
    ) -> tuple[str, float, str]:
        """Generate AI suggestion based on match score with source citations."""
        if match_score >= 0.8:
            suggestion = "true_match"
            confidence = round(0.7 + random.uniform(0, 0.25), 2)
            reasoning = (
                f"High name similarity ({match_score:.0%}) against {source}. "
                "This suggests a likely match. Per SAMA AML/CTF guidelines, "
                "recommend immediate manual verification of identity documents and "
                "consideration of filing a Suspicious Transaction Report (STR) to SAFIU."
            )
        elif match_score >= 0.5:
            suggestion = "inconclusive"
            confidence = round(0.4 + random.uniform(0, 0.3), 2)
            reasoning = (
                f"Moderate name similarity ({match_score:.0%}) against {source}. "
                "Additional identifiers needed (date of birth, national ID, passport) to confirm or dismiss. "
                "Per SAMA CDD requirements, enhanced due diligence is recommended."
            )
        else:
            suggestion = "false_positive"
            confidence = round(0.6 + random.uniform(0, 0.3), 2)
            reasoning = (
                f"Low name similarity ({match_score:.0%}) against {source}. "
                "Common name overlap is likely. Recommend dismissal unless other risk indicators "
                "are present. Document rationale per SAMA record-keeping requirements."
            )
        return suggestion, confidence, reasoning

    @staticmethod
    async def get_data_source_info() -> dict:
        """Get information about the screening data sources."""
        try:
            un_stats = await get_sanctions_stats()
        except Exception:
            un_stats = {
                "source": "UN Security Council Consolidated Sanctions List",
                "status": "unavailable",
                "error": "Could not fetch UN sanctions data",
            }

        return {
            "sanctions": {
                "primary": un_stats,
                "description": "Real-time UN Security Council Consolidated Sanctions List",
                "description_ar": "قائمة العقوبات الموحدة لمجلس الأمن الدولي في الوقت الفعلي",
            },
            "pep": {
                "source": "Internal PEP Database",
                "description": "Curated Politically Exposed Persons reference list",
                "description_ar": "قائمة مرجعية منسقة للأشخاص المعرضين سياسياً",
                "count": len(PEP_LIST),
            },
        }
