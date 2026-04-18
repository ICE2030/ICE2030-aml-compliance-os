"""UN Security Council Consolidated Sanctions List Service.
Fetches and parses the official UN SC sanctions list (XML format) for real-time screening.
Source: https://scsanctions.un.org/resources/xml/en/consolidated.xml
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from lxml import etree

import httpx

logger = logging.getLogger(__name__)

UN_SANCTIONS_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"

# Cache for parsed sanctions data
_sanctions_cache: dict = {
    "individuals": [],
    "entities": [],
    "last_updated": None,
    "total_count": 0,
}
_cache_lock = asyncio.Lock()
CACHE_TTL_SECONDS = 3600  # Refresh every hour


def _parse_name_parts(element: etree._Element) -> str:
    """Extract full name from INDIVIDUAL or ENTITY element."""
    # For individuals
    first = element.findtext(".//FIRST_NAME") or ""
    second = element.findtext(".//SECOND_NAME") or ""
    third = element.findtext(".//THIRD_NAME") or ""
    fourth = element.findtext(".//FOURTH_NAME") or ""
    parts = [p.strip() for p in [first, second, third, fourth] if p.strip()]
    if parts:
        return " ".join(parts)
    # For entities - use FIRST_NAME which contains the entity name
    name = element.findtext(".//FIRST_NAME") or ""
    return name.strip()


def _extract_aliases(element: etree._Element) -> list[dict]:
    """Extract aliases from an individual or entity."""
    aliases = []
    for alias_elem in element.findall(".//INDIVIDUAL_ALIAS") + element.findall(".//ENTITY_ALIAS"):
        quality = alias_elem.findtext("QUALITY") or "Unknown"
        alias_name = alias_elem.findtext("ALIAS_NAME") or ""
        if alias_name.strip():
            aliases.append({"name": alias_name.strip(), "quality": quality})
    return aliases


def _parse_individual(elem: etree._Element) -> dict:
    """Parse an INDIVIDUAL element into a structured dict."""
    dataid = elem.findtext("DATAID") or ""
    ref_number = elem.findtext("REFERENCE_NUMBER") or ""
    listed_on = elem.findtext("LISTED_ON") or ""
    comments = elem.findtext("COMMENTS1") or ""

    name = _parse_name_parts(elem)
    aliases = _extract_aliases(elem)

    # Nationalities
    nationalities = []
    for nat in elem.findall(".//NATIONALITY/VALUE"):
        if nat.text:
            nationalities.append(nat.text.strip())

    # Date of birth
    dobs = []
    for dob in elem.findall(".//INDIVIDUAL_DATE_OF_BIRTH"):
        date_val = dob.findtext("DATE") or dob.findtext("YEAR") or ""
        if date_val:
            dobs.append(date_val.strip())

    # UN list type
    un_list = elem.findtext("UN_LIST_TYPE") or ""
    sort_key = elem.findtext("SORT_KEY") or ""

    return {
        "type": "individual",
        "dataid": dataid,
        "reference_number": ref_number,
        "name": name,
        "aliases": aliases,
        "listed_on": listed_on,
        "nationalities": nationalities,
        "dates_of_birth": dobs,
        "un_list_type": un_list,
        "sort_key": sort_key,
        "comments": comments[:500] if comments else "",
        "source": "UN Security Council",
        "source_url": "https://www.un.org/securitycouncil/content/un-sc-consolidated-list",
    }


def _parse_entity(elem: etree._Element) -> dict:
    """Parse an ENTITY element into a structured dict."""
    dataid = elem.findtext("DATAID") or ""
    ref_number = elem.findtext("REFERENCE_NUMBER") or ""
    listed_on = elem.findtext("LISTED_ON") or ""
    comments = elem.findtext("COMMENTS1") or ""
    first_name = elem.findtext(".//FIRST_NAME") or ""
    aliases = _extract_aliases(elem)
    un_list = elem.findtext("UN_LIST_TYPE") or ""
    sort_key = elem.findtext("SORT_KEY") or ""

    return {
        "type": "entity",
        "dataid": dataid,
        "reference_number": ref_number,
        "name": first_name.strip(),
        "aliases": aliases,
        "listed_on": listed_on,
        "un_list_type": un_list,
        "sort_key": sort_key,
        "comments": comments[:500] if comments else "",
        "source": "UN Security Council",
        "source_url": "https://www.un.org/securitycouncil/content/un-sc-consolidated-list",
    }


async def fetch_un_sanctions() -> dict:
    """Fetch and parse the UN SC Consolidated Sanctions List."""
    global _sanctions_cache

    async with _cache_lock:
        now = datetime.now(timezone.utc)
        if (
            _sanctions_cache["last_updated"]
            and (now - _sanctions_cache["last_updated"]).total_seconds() < CACHE_TTL_SECONDS
            and _sanctions_cache["total_count"] > 0
        ):
            return _sanctions_cache

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(UN_SANCTIONS_XML_URL)
            response.raise_for_status()

        root = etree.fromstring(response.content)

        individuals = []
        for elem in root.findall(".//INDIVIDUAL"):
            parsed = _parse_individual(elem)
            if parsed["name"]:
                individuals.append(parsed)

        entities = []
        for elem in root.findall(".//ENTITY"):
            parsed = _parse_entity(elem)
            if parsed["name"]:
                entities.append(parsed)

        async with _cache_lock:
            _sanctions_cache = {
                "individuals": individuals,
                "entities": entities,
                "last_updated": datetime.now(timezone.utc),
                "total_count": len(individuals) + len(entities),
            }

        logger.info(
            f"UN Sanctions list updated: {len(individuals)} individuals, "
            f"{len(entities)} entities"
        )
        return _sanctions_cache

    except Exception as e:
        logger.error(f"Failed to fetch UN sanctions list: {e}")
        if _sanctions_cache["total_count"] > 0:
            return _sanctions_cache
        raise


def fuzzy_match_name(query: str, target: str) -> float:
    """Enhanced fuzzy name matching with token overlap and partial matching."""
    q_tokens = set(query.lower().split())
    t_tokens = set(target.lower().split())
    if not q_tokens or not t_tokens:
        return 0.0

    # Jaccard similarity
    intersection = q_tokens & t_tokens
    union = q_tokens | t_tokens
    jaccard = len(intersection) / len(union) if union else 0.0

    # Partial substring matching boost
    partial = 0
    for qt in q_tokens:
        for tt in t_tokens:
            if len(qt) >= 3 and len(tt) >= 3:
                if qt in tt or tt in qt:
                    partial += 1
    partial_boost = min(partial * 0.15, 0.3)

    return min(jaccard + partial_boost, 1.0)


async def screen_against_un_sanctions(
    name: str, threshold: float = 0.25
) -> list[dict]:
    """Screen a name against the UN Consolidated Sanctions List.

    Returns list of matches above the threshold with match scores.
    """
    data = await fetch_un_sanctions()
    matches = []

    all_entries = data["individuals"] + data["entities"]

    for entry in all_entries:
        # Match against primary name
        score = fuzzy_match_name(name, entry["name"])

        # Also check aliases for better match
        for alias in entry.get("aliases", []):
            alias_score = fuzzy_match_name(name, alias["name"])
            if alias_score > score:
                score = alias_score

        if score >= threshold:
            matches.append({
                **entry,
                "match_score": round(score, 3),
                "matched_against": name,
            })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:20]  # Return top 20 matches


async def get_sanctions_stats() -> dict:
    """Get current stats about the loaded sanctions data."""
    data = await fetch_un_sanctions()
    return {
        "source": "UN Security Council Consolidated Sanctions List",
        "source_url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        "individuals_count": len(data["individuals"]),
        "entities_count": len(data["entities"]),
        "total_count": data["total_count"],
        "last_updated": data["last_updated"].isoformat() if data["last_updated"] else None,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }
