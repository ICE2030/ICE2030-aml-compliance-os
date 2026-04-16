"""Seed Service - loads regulator pack data into the database.

Hardened for Phase 2 readiness:
- Deterministic seed_key matching (Fix 4): Sources are matched by seed_key (pack_id:source_key)
  instead of title, preventing duplicate drift when titles change.
- Pack provenance (Fix 3): Each seeded source records its pack_id origin.
- Source-topic wiring (Fix 1): Populates the source_topics junction table from pack definitions.
- Backward compatible: Existing title-matched sources are migrated to seed_key on re-seed.
"""
import logging
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.source import (
    Jurisdiction, Regulator, Source, RegulatoryDocument, Provision, Topic,
    SourceType, AuthorityLevel, SourceStatus, CrawlFrequency, ProvisionType,
    SourceTopic,
)
from regulator_packs.base_pack import RegulatorPack, SourceDef
from regulator_packs.pack_loader import load_all_packs

logger = logging.getLogger(__name__)


def _make_seed_key(pack_id: str, source_def: SourceDef) -> str:
    """Build a deterministic seed_key from pack_id and source key.

    If the source defines an explicit key, use it. Otherwise, generate one
    from a slugified title (for backward compatibility with packs that
    haven't added keys yet).
    """
    if source_def.key:
        source_key = source_def.key
    else:
        # Fallback: slugify the title
        source_key = re.sub(r'[^a-z0-9]+', '_', source_def.title.lower()).strip('_')
    return f"{pack_id}:{source_key}"


class SeedService:
    """Seeds the database with regulator pack data."""

    @staticmethod
    async def seed_pack(db: AsyncSession, pack: RegulatorPack) -> dict:
        """Seed a single regulator pack into the database."""
        stats = {
            "jurisdictions": 0, "regulators": 0, "sources": 0,
            "topics": 0, "provisions": 0, "source_topics": 0,
            "sources_updated": 0,
        }

        # 1. Ensure jurisdiction exists
        result = await db.execute(
            select(Jurisdiction).where(Jurisdiction.code == pack.jurisdiction.code)
        )
        jurisdiction = result.scalar_one_or_none()
        if not jurisdiction:
            jurisdiction = Jurisdiction(
                name=pack.jurisdiction.name,
                name_ar=pack.jurisdiction.name_ar,
                code=pack.jurisdiction.code,
                region=pack.jurisdiction.region,
            )
            db.add(jurisdiction)
            await db.flush()
            stats["jurisdictions"] += 1

        # 2. Ensure regulator exists
        result = await db.execute(
            select(Regulator).where(Regulator.abbreviation == pack.regulator.abbreviation)
        )
        regulator = result.scalar_one_or_none()
        if not regulator:
            regulator = Regulator(
                name=pack.regulator.name,
                name_ar=pack.regulator.name_ar,
                abbreviation=pack.regulator.abbreviation,
                jurisdiction_id=jurisdiction.id,
                website=pack.regulator.website,
                source_url=pack.regulator.source_url,
                regulator_type=pack.regulator.regulator_type,
                description=pack.regulator.description,
                description_ar=pack.regulator.description_ar,
            )
            db.add(regulator)
            await db.flush()
            stats["regulators"] += 1

        # 3. Create topics (before sources, so we can link them)
        topic_name_to_id: dict[str, str] = {}
        for topic_def in pack.topics:
            result = await db.execute(
                select(Topic).where(Topic.name == topic_def.name)
            )
            existing_topic = result.scalar_one_or_none()
            if existing_topic:
                topic_name_to_id[topic_def.name] = existing_topic.id
                continue

            topic = Topic(
                name=topic_def.name,
                name_ar=topic_def.name_ar,
                category=topic_def.category,
                description=topic_def.description,
            )
            db.add(topic)
            await db.flush()
            topic_name_to_id[topic_def.name] = topic.id
            stats["topics"] += 1

        # 4. Create or update sources with deterministic seed_key matching
        for src_def in pack.sources:
            seed_key = _make_seed_key(pack.pack_id, src_def)

            # Try to find by seed_key first (deterministic)
            result = await db.execute(
                select(Source).where(Source.seed_key == seed_key)
            )
            source = result.scalar_one_or_none()

            if not source:
                # Backward compat: try legacy title+regulator match and migrate
                result = await db.execute(
                    select(Source).where(
                        Source.title == src_def.title,
                        Source.regulator_id == regulator.id,
                        Source.seed_key.is_(None),
                    )
                )
                source = result.scalar_one_or_none()
                if source:
                    # Migrate legacy record to seed_key
                    source.seed_key = seed_key
                    source.pack_id = pack.pack_id
                    stats["sources_updated"] += 1
                    logger.info(f"Migrated legacy source to seed_key: {seed_key}")

            if not source:
                # Create new source
                try:
                    source_type = SourceType(src_def.source_type)
                except (ValueError, KeyError):
                    source_type = SourceType.REGULATION

                try:
                    authority = AuthorityLevel(src_def.authority_level)
                except (ValueError, KeyError):
                    authority = AuthorityLevel.TIER_1

                try:
                    freq = CrawlFrequency(src_def.crawl_frequency)
                except (ValueError, KeyError):
                    freq = CrawlFrequency.WEEKLY

                source = Source(
                    regulator_id=regulator.id,
                    title=src_def.title,
                    title_ar=src_def.title_ar,
                    url=src_def.url,
                    source_type=source_type,
                    authority_level=authority,
                    jurisdiction_id=jurisdiction.id,
                    language=src_def.language,
                    is_monitored=True,
                    crawl_frequency=freq,
                    status=SourceStatus.ACTIVE,
                    parser_config=src_def.parser_config or {},
                    pack_id=pack.pack_id,
                    seed_key=seed_key,
                )
                db.add(source)
                await db.flush()
                stats["sources"] += 1

            # 5. Wire source_topics (Fix 1) — idempotent
            if src_def.topic_names:
                for topic_name in src_def.topic_names:
                    topic_id = topic_name_to_id.get(topic_name)
                    if not topic_id:
                        # Topic may have been created by another pack — look it up
                        result = await db.execute(
                            select(Topic).where(Topic.name == topic_name)
                        )
                        found_topic = result.scalar_one_or_none()
                        if found_topic:
                            topic_id = found_topic.id
                            topic_name_to_id[topic_name] = topic_id
                        else:
                            logger.warning(f"Topic not found for source-topic link: {topic_name}")
                            continue

                    # Check if link already exists
                    result = await db.execute(
                        select(SourceTopic).where(
                            SourceTopic.source_id == source.id,
                            SourceTopic.topic_id == topic_id,
                        )
                    )
                    if not result.scalar_one_or_none():
                        db.add(SourceTopic(source_id=source.id, topic_id=topic_id))
                        stats["source_topics"] += 1

        await db.flush()

        # 6. Create sample provisions (linked to a seed document)
        if pack.sample_provisions:
            doc_title = f"{pack.regulator.name} - Seed Provisions"
            result = await db.execute(
                select(RegulatoryDocument).where(RegulatoryDocument.title == doc_title)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                doc = RegulatoryDocument(
                    source_version_id=None,  # Seed data, no crawled version
                    title=doc_title,
                    title_ar=f"{pack.regulator.name_ar} - أحكام أولية",
                    document_type="seed_fixture",
                    regulator_id=regulator.id,
                    jurisdiction_id=jurisdiction.id,
                    language=pack.sources[0].language if pack.sources else "en",
                )
                db.add(doc)
                await db.flush()

                for i, prov_def in enumerate(pack.sample_provisions):
                    try:
                        prov_type = ProvisionType(prov_def.provision_type)
                    except (ValueError, KeyError):
                        prov_type = ProvisionType.ARTICLE

                    prov = Provision(
                        document_id=doc.id,
                        section_number=prov_def.section_number,
                        title=prov_def.title,
                        title_ar=prov_def.title_ar,
                        text=prov_def.text,
                        text_ar=prov_def.text_ar,
                        provision_type=prov_type,
                        order_index=i,
                    )
                    db.add(prov)
                    stats["provisions"] += 1

        await db.flush()
        return stats

    @staticmethod
    async def seed_all_packs(db: AsyncSession) -> dict:
        """Seed all available regulator packs."""
        packs = load_all_packs()
        total_stats = {
            "packs_loaded": 0, "jurisdictions": 0, "regulators": 0,
            "sources": 0, "topics": 0, "provisions": 0,
            "source_topics": 0, "sources_updated": 0,
        }

        for pack in packs:
            try:
                stats = await SeedService.seed_pack(db, pack)
                total_stats["packs_loaded"] += 1
                for key in stats:
                    total_stats[key] += stats[key]
                logger.info(f"Seeded pack {pack.pack_id}: {stats}")
            except Exception as e:
                logger.error(f"Failed to seed pack {pack.pack_id}: {e}")

        return total_stats
