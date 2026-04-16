"""Change detection, review, and query log models."""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class ChangeType(str, enum.Enum):
    NEW_DOCUMENT = "new_document"
    CONTENT_MODIFIED = "content_modified"
    SECTION_ADDED = "section_added"
    SECTION_REMOVED = "section_removed"
    SECTION_MODIFIED = "section_modified"
    METADATA_CHANGED = "metadata_changed"


class ImpactLevel(str, enum.Enum):
    INFORMATIONAL = "informational"
    INTERPRETIVE = "interpretive"
    OPERATIONAL = "operational"
    MATERIAL = "material"


class ReviewDecisionType(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class ChangeEvent(Base, TimestampMixin):
    __tablename__ = "change_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("regulatory_sources.id"))
    old_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_versions.id"), nullable=True)
    new_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType))
    impact_level: Mapped[ImpactLevel] = mapped_column(Enum(ImpactLevel), default=ImpactLevel.INFORMATIONAL)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_provisions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    affected_obligations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    affected_topics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewDecision(Base, TimestampMixin):
    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    content_type: Mapped[str] = mapped_column(String(100))  # obligation, change_event, provision
    content_id: Mapped[str] = mapped_column(String(36))
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    decision: Mapped[ReviewDecisionType] = mapped_column(Enum(ReviewDecisionType))
    confidence_adjustment: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QueryLog(Base, TimestampMixin):
    __tablename__ = "query_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    query_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sources_used: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    gaps_detected: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    feedback_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
