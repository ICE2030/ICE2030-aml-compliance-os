"""Source Registry Service - manages regulatory sources and their versions."""
import hashlib
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.regulatory.source import (
    Jurisdiction, Regulator, Source, SourceVersion, RegulatoryDocument, Provision, Topic,
    SourceType, AuthorityLevel, SourceStatus, CrawlFrequency, SourceTopic,
)


class SourceRegistryService:
    """Manages the registry of regulatory sources."""

    @staticmethod
    async def get_jurisdictions(db: AsyncSession) -> list[Jurisdiction]:
        result = await db.execute(select(Jurisdiction).order_by(Jurisdiction.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_jurisdiction_by_code(db: AsyncSession, code: str) -> Optional[Jurisdiction]:
        result = await db.execute(select(Jurisdiction).where(Jurisdiction.code == code))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_jurisdiction(db: AsyncSession, name: str, code: str, name_ar: str = None, region: str = None) -> Jurisdiction:
        j = Jurisdiction(name=name, name_ar=name_ar, code=code, region=region)
        db.add(j)
        await db.flush()
        return j

    @staticmethod
    async def get_regulators(db: AsyncSession, jurisdiction_id: str = None) -> list[Regulator]:
        q = select(Regulator).options(selectinload(Regulator.jurisdiction))
        if jurisdiction_id:
            q = q.where(Regulator.jurisdiction_id == jurisdiction_id)
        result = await db.execute(q.order_by(Regulator.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_regulator_by_abbr(db: AsyncSession, abbreviation: str) -> Optional[Regulator]:
        result = await db.execute(select(Regulator).where(Regulator.abbreviation == abbreviation))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_regulator(db: AsyncSession, name: str, abbreviation: str, jurisdiction_id: str, **kwargs) -> Regulator:
        r = Regulator(name=name, abbreviation=abbreviation, jurisdiction_id=jurisdiction_id, **kwargs)
        db.add(r)
        await db.flush()
        return r

    @staticmethod
    async def get_sources(
        db: AsyncSession,
        regulator_id: str = None,
        source_type: str = None,
        authority_level: str = None,
        status: str = None,
        is_monitored: bool = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Source], int]:
        q = select(Source).options(selectinload(Source.regulator))
        count_q = select(func.count(Source.id))

        if regulator_id:
            q = q.where(Source.regulator_id == regulator_id)
            count_q = count_q.where(Source.regulator_id == regulator_id)
        if source_type:
            q = q.where(Source.source_type == source_type)
            count_q = count_q.where(Source.source_type == source_type)
        if authority_level:
            q = q.where(Source.authority_level == authority_level)
            count_q = count_q.where(Source.authority_level == authority_level)
        if status:
            q = q.where(Source.status == status)
            count_q = count_q.where(Source.status == status)
        if is_monitored is not None:
            q = q.where(Source.is_monitored == is_monitored)
            count_q = count_q.where(Source.is_monitored == is_monitored)

        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(q.order_by(Source.created_at.desc()).offset(skip).limit(limit))
        return list(result.scalars().all()), total

    @staticmethod
    async def get_source_by_id(db: AsyncSession, source_id: str) -> Optional[Source]:
        result = await db.execute(
            select(Source)
            .options(selectinload(Source.regulator), selectinload(Source.versions))
            .where(Source.id == source_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_source(db: AsyncSession, **kwargs) -> Source:
        s = Source(**kwargs)
        db.add(s)
        await db.flush()
        return s

    # Allowed fields for source updates
    _SOURCE_UPDATABLE_FIELDS = frozenset({
        "title", "title_ar", "url", "source_type", "authority_level",
        "language", "crawl_frequency", "is_monitored", "status",
        "parser_config", "metadata_extra",
    })

    @staticmethod
    async def update_source(db: AsyncSession, source_id: str, **kwargs) -> Optional[Source]:
        source = await SourceRegistryService.get_source_by_id(db, source_id)
        if not source:
            return None
        allowed = SourceRegistryService._SOURCE_UPDATABLE_FIELDS
        for field_name in allowed:
            if field_name in kwargs:
                # Direct column descriptor assignment for proper SQLAlchemy dirty tracking
                if field_name == "title":
                    source.title = kwargs[field_name]
                elif field_name == "title_ar":
                    source.title_ar = kwargs[field_name]
                elif field_name == "url":
                    source.url = kwargs[field_name]
                elif field_name == "source_type":
                    source.source_type = kwargs[field_name]
                elif field_name == "authority_level":
                    source.authority_level = kwargs[field_name]
                elif field_name == "language":
                    source.language = kwargs[field_name]
                elif field_name == "crawl_frequency":
                    source.crawl_frequency = kwargs[field_name]
                elif field_name == "is_monitored":
                    source.is_monitored = kwargs[field_name]
                elif field_name == "status":
                    source.status = kwargs[field_name]
                elif field_name == "parser_config":
                    source.parser_config = kwargs[field_name]
                elif field_name == "metadata_extra":
                    source.metadata_extra = kwargs[field_name]
        await db.flush()
        return source

    @staticmethod
    async def delete_source(db: AsyncSession, source_id: str) -> bool:
        """Delete a source by ID. Returns True if deleted, False if not found."""
        source = await SourceRegistryService.get_source_by_id(db, source_id)
        if not source:
            return False
        await db.delete(source)
        await db.flush()
        return True

    @staticmethod
    async def create_source_version(
        db: AsyncSession,
        source_id: str,
        raw_content: str,
        parsed_content: str = None,
        parser_confidence: float = None,
    ) -> SourceVersion:
        # Get current max version
        result = await db.execute(
            select(func.max(SourceVersion.version_number))
            .where(SourceVersion.source_id == source_id)
        )
        max_ver = result.scalar() or 0

        # Mark previous versions as not current
        prev_versions = await db.execute(
            select(SourceVersion)
            .where(SourceVersion.source_id == source_id, SourceVersion.is_current == True)
        )
        for v in prev_versions.scalars().all():
            v.is_current = False

        content_hash = hashlib.sha256(raw_content.encode()).hexdigest()
        sv = SourceVersion(
            source_id=source_id,
            version_number=max_ver + 1,
            fetched_at=datetime.now(timezone.utc),
            content_hash=content_hash,
            raw_content=raw_content,
            parsed_content=parsed_content,
            is_current=True,
            parser_confidence=parser_confidence,
        )
        db.add(sv)
        await db.flush()

        # Update source last_crawled
        source = await db.get(Source, source_id)
        if source:
            source.last_crawled = datetime.now(timezone.utc)
            source.last_crawl_status = "success"

        return sv

    @staticmethod
    async def get_source_versions(db: AsyncSession, source_id: str) -> list[SourceVersion]:
        result = await db.execute(
            select(SourceVersion)
            .where(SourceVersion.source_id == source_id)
            .order_by(SourceVersion.version_number.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_topics(db: AsyncSession, category: str = None) -> list[Topic]:
        q = select(Topic)
        if category:
            q = q.where(Topic.category == category)
        result = await db.execute(q.order_by(Topic.name))
        return list(result.scalars().all())

    @staticmethod
    async def create_topic(db: AsyncSession, name: str, category: str, **kwargs) -> Topic:
        t = Topic(name=name, category=category, **kwargs)
        db.add(t)
        await db.flush()
        return t

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> dict:
        """Get summary statistics for the regulatory intelligence dashboard."""
        sources_count = (await db.execute(select(func.count(Source.id)))).scalar() or 0
        monitored_count = (await db.execute(
            select(func.count(Source.id)).where(Source.is_monitored == True)
        )).scalar() or 0
        regulators_count = (await db.execute(select(func.count(Regulator.id)))).scalar() or 0
        jurisdictions_count = (await db.execute(select(func.count(Jurisdiction.id)))).scalar() or 0
        documents_count = (await db.execute(select(func.count(RegulatoryDocument.id)))).scalar() or 0
        provisions_count = (await db.execute(select(func.count(Provision.id)))).scalar() or 0
        topics_count = (await db.execute(select(func.count(Topic.id)))).scalar() or 0

        # Sources by status
        status_result = await db.execute(
            select(Source.status, func.count(Source.id)).group_by(Source.status)
        )
        sources_by_status = {row[0]: row[1] for row in status_result.all()}

        # Sources by authority level
        authority_result = await db.execute(
            select(Source.authority_level, func.count(Source.id)).group_by(Source.authority_level)
        )
        sources_by_authority = {row[0]: row[1] for row in authority_result.all()}

        return {
            "total_sources": sources_count,
            "monitored_sources": monitored_count,
            "total_regulators": regulators_count,
            "total_jurisdictions": jurisdictions_count,
            "total_documents": documents_count,
            "total_provisions": provisions_count,
            "total_topics": topics_count,
            "sources_by_status": sources_by_status,
            "sources_by_authority": sources_by_authority,
        }
