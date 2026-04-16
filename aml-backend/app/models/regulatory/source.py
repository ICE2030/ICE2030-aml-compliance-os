"""Source registry and document models for regulatory intelligence."""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class AuthorityLevel(str, enum.Enum):
    TIER_1 = "tier_1"  # Official binding (laws, regulations)
    TIER_2 = "tier_2"  # Official guidance (FAQs, circulars)
    TIER_3 = "tier_3"  # Draft / consultation
    TIER_4 = "tier_4"  # Secondary commentary


class SourceType(str, enum.Enum):
    LAW = "law"
    REGULATION = "regulation"
    RULEBOOK = "rulebook"
    CIRCULAR = "circular"
    GUIDANCE = "guidance"
    FAQ = "faq"
    CONSULTATION = "consultation"
    ENFORCEMENT = "enforcement"
    SPEECH = "speech"
    NOTICE = "notice"


class SourceStatus(str, enum.Enum):
    ACTIVE = "active"
    MONITORING = "monitoring"
    PAUSED = "paused"
    ERROR = "error"
    ARCHIVED = "archived"


class CrawlFrequency(str, enum.Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MANUAL = "manual"


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REPEALED = "repealed"


class ProvisionType(str, enum.Enum):
    ARTICLE = "article"
    CLAUSE = "clause"
    SECTION = "section"
    DEFINITION = "definition"
    SCHEDULE = "schedule"
    ANNEX = "annex"
    CHAPTER = "chapter"


class Jurisdiction(Base, TimestampMixin):
    __tablename__ = "jurisdictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)  # ISO 3166
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    regulators: Mapped[list["Regulator"]] = relationship(back_populates="jurisdiction")


class Regulator(Base, TimestampMixin):
    __tablename__ = "regulators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(300))
    name_ar: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    abbreviation: Mapped[str] = mapped_column(String(50))
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("jurisdictions.id"))
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    regulator_type: Mapped[str] = mapped_column(String(100), default="financial")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="regulators")
    sources: Mapped[list["Source"]] = relationship(back_populates="regulator")


class Source(Base, TimestampMixin):
    __tablename__ = "regulatory_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    regulator_id: Mapped[str] = mapped_column(ForeignKey("regulators.id"))
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType))
    authority_level: Mapped[AuthorityLevel] = mapped_column(Enum(AuthorityLevel))
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("jurisdictions.id"))
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    crawl_frequency: Mapped[CrawlFrequency] = mapped_column(Enum(CrawlFrequency), default=CrawlFrequency.DAILY)
    last_crawled: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_crawl_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[SourceStatus] = mapped_column(Enum(SourceStatus), default=SourceStatus.ACTIVE)
    parser_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    regulator: Mapped["Regulator"] = relationship(back_populates="sources")
    versions: Mapped[list["SourceVersion"]] = relationship(back_populates="source", order_by="SourceVersion.version_number.desc()")
    topics: Mapped[list["SourceTopic"]] = relationship(back_populates="source")


class SourceVersion(Base, TimestampMixin):
    __tablename__ = "source_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("regulatory_sources.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    parser_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    source: Mapped["Source"] = relationship(back_populates="versions")
    documents: Mapped[list["RegulatoryDocument"]] = relationship(back_populates="source_version")


class RegulatoryDocument(Base, TimestampMixin):
    __tablename__ = "regulatory_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_versions.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    document_type: Mapped[str] = mapped_column(String(100))
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    regulator_id: Mapped[str] = mapped_column(ForeignKey("regulators.id"))
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("jurisdictions.id"))
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.ACTIVE)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    source_version: Mapped["SourceVersion"] = relationship(back_populates="documents")
    provisions: Mapped[list["Provision"]] = relationship(back_populates="reg_document", order_by="Provision.order_index")
    topics: Mapped[list["DocumentTopic"]] = relationship(back_populates="reg_document")


class Provision(Base, TimestampMixin):
    __tablename__ = "provisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("regulatory_documents.id"))
    section_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    text_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provision_type: Mapped[ProvisionType] = mapped_column(Enum(ProvisionType), default=ProvisionType.ARTICLE)
    parent_provision_id: Mapped[Optional[str]] = mapped_column(ForeignKey("provisions.id"), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    reg_document: Mapped["RegulatoryDocument"] = relationship(back_populates="provisions")
    children: Mapped[list["Provision"]] = relationship(back_populates="parent")
    parent: Mapped[Optional["Provision"]] = relationship(back_populates="children", remote_side="Provision.id")


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    name_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    category: Mapped[str] = mapped_column(String(100))  # aml, ctf, kyc, sanctions, pep, reporting, governance, fintech, data_protection, licensing
    parent_topic_id: Mapped[Optional[str]] = mapped_column(ForeignKey("topics.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    children: Mapped[list["Topic"]] = relationship(back_populates="parent")
    parent: Mapped[Optional["Topic"]] = relationship(back_populates="children", remote_side="Topic.id")


class SourceTopic(Base):
    __tablename__ = "source_topics"

    source_id: Mapped[str] = mapped_column(ForeignKey("regulatory_sources.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), primary_key=True)

    source: Mapped["Source"] = relationship(back_populates="topics")
    topic: Mapped["Topic"] = relationship()


class DocumentTopic(Base):
    __tablename__ = "document_topics"

    document_id: Mapped[str] = mapped_column(ForeignKey("regulatory_documents.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), primary_key=True)

    reg_document: Mapped["RegulatoryDocument"] = relationship(back_populates="topics")
    topic: Mapped["Topic"] = relationship()
