"""Pattern Detection Engine - identifies recurring risk patterns, clusters, anomalies."""
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.entity import Entity, OwnershipLink, RiskLevel
from app.models.screening import ScreeningResult, MatchStatus
from app.models.case import Case
from app.models.interaction import PatternDetection
from app.models.base import generate_uuid


class PatternDetectionService:
    @staticmethod
    async def detect_all_patterns(db: AsyncSession) -> list[PatternDetection]:
        """Run all pattern detection algorithms."""
        patterns = []
        patterns.extend(await PatternDetectionService._detect_ownership_clusters(db))
        patterns.extend(await PatternDetectionService._detect_repeated_behaviors(db))
        patterns.extend(await PatternDetectionService._detect_high_risk_clusters(db))
        patterns.extend(await PatternDetectionService._detect_geographic_patterns(db))
        return patterns

    @staticmethod
    async def _detect_ownership_clusters(db: AsyncSession) -> list[PatternDetection]:
        """Find entities with shared ownership structures."""
        patterns = []
        # Find entities with multiple ownership links
        result = await db.execute(
            select(
                OwnershipLink.parent_entity_id,
                func.count(OwnershipLink.child_entity_id).label("child_count")
            ).group_by(OwnershipLink.parent_entity_id)
            .having(func.count(OwnershipLink.child_entity_id) >= 2)
        )
        clusters = result.all()

        for parent_id, child_count in clusters:
            parent_result = await db.execute(select(Entity).where(Entity.id == parent_id))
            parent = parent_result.scalar_one_or_none()
            if not parent:
                continue

            children_result = await db.execute(
                select(OwnershipLink).where(OwnershipLink.parent_entity_id == parent_id)
            )
            links = children_result.scalars().all()
            child_ids = [l.child_entity_id for l in links]

            pattern = PatternDetection(
                id=generate_uuid(),
                pattern_type="ownership_cluster",
                title=f"Ownership cluster: {parent.name} controls {child_count} entities",
                description=f"Entity '{parent.name}' has ownership links to {child_count} other entities. "
                           "Review for potential layered ownership structures.",
                severity="medium" if child_count < 5 else "high",
                affected_entities={"parent": parent_id, "children": child_ids},
                pattern_data={"total_links": child_count},
            )
            db.add(pattern)
            patterns.append(pattern)

        return patterns

    @staticmethod
    async def _detect_repeated_behaviors(db: AsyncSession) -> list[PatternDetection]:
        """Find entities with repeated screening matches or cases."""
        patterns = []
        # Entities with multiple true matches
        result = await db.execute(
            select(
                ScreeningResult.entity_id,
                func.count(ScreeningResult.id).label("match_count")
            ).where(ScreeningResult.status == MatchStatus.TRUE_MATCH)
            .group_by(ScreeningResult.entity_id)
            .having(func.count(ScreeningResult.id) >= 2)
        )
        repeat_offenders = result.all()

        for entity_id, match_count in repeat_offenders:
            entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
            entity = entity_result.scalar_one_or_none()
            if not entity:
                continue

            pattern = PatternDetection(
                id=generate_uuid(),
                pattern_type="behavioral",
                title=f"Repeated screening matches: {entity.name}",
                description=f"Entity has {match_count} confirmed screening matches across different lists.",
                severity="high",
                affected_entities={"entity_id": entity_id},
                pattern_data={"match_count": match_count},
            )
            db.add(pattern)
            patterns.append(pattern)

        return patterns

    @staticmethod
    async def _detect_high_risk_clusters(db: AsyncSession) -> list[PatternDetection]:
        """Find clusters of high-risk entities in same industry/country."""
        patterns = []
        # Group high-risk entities by industry
        result = await db.execute(
            select(
                Entity.industry,
                func.count(Entity.id).label("entity_count")
            ).where(
                Entity.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]),
                Entity.industry.isnot(None)
            ).group_by(Entity.industry)
            .having(func.count(Entity.id) >= 2)
        )
        clusters = result.all()

        for industry, count in clusters:
            pattern = PatternDetection(
                id=generate_uuid(),
                pattern_type="risk_cluster",
                title=f"High-risk cluster in {industry}: {count} entities",
                description=f"{count} high/critical risk entities found in the {industry} industry.",
                severity="high",
                affected_entities={"industry": industry},
                pattern_data={"industry": industry, "entity_count": count},
            )
            db.add(pattern)
            patterns.append(pattern)

        return patterns

    @staticmethod
    async def _detect_geographic_patterns(db: AsyncSession) -> list[PatternDetection]:
        """Find geographic concentrations of risk."""
        patterns = []
        result = await db.execute(
            select(
                Entity.country,
                func.count(Entity.id).label("entity_count"),
            ).where(
                Entity.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL])
            ).group_by(Entity.country)
            .having(func.count(Entity.id) >= 2)
        )
        geo_clusters = result.all()

        for country, count in geo_clusters:
            pattern = PatternDetection(
                id=generate_uuid(),
                pattern_type="geographic",
                title=f"Geographic risk concentration: {country} ({count} entities)",
                description=f"{count} high-risk entities concentrated in country code {country}.",
                severity="medium",
                affected_entities={"country": country},
                pattern_data={"country": country, "entity_count": count},
            )
            db.add(pattern)
            patterns.append(pattern)

        return patterns
