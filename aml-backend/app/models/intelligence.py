"""Phase 3: Decision Intelligence models.

Stores structured decision captures, case memory embeddings,
and intelligence metrics for the self-improving loops.
"""
from sqlalchemy import String, Float, Integer, Text, JSON, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from typing import Optional
from datetime import datetime


class DecisionCapture(Base, TimestampMixin):
    """Structured capture of every case resolution decision.

    Extends the basic case.decision with:
    - reasoning categories (structured + free text)
    - AI suggestion disposition (accepted / edited / rejected)
    - user confidence score
    - per-step time breakdown
    """
    __tablename__ = "decision_captures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

    # Core decision
    decision: Mapped[str] = mapped_column(String(50))  # approve / reject / escalate / sar_filed / no_action
    reasoning_text: Mapped[str] = mapped_column(Text)
    reasoning_categories: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # e.g. {"risk_factors": true, "screening_match": false, "regulatory_concern": true, "insufficient_info": false}

    # User confidence
    user_confidence: Mapped[float] = mapped_column(Float)  # 0-1

    # Timing
    time_to_decision_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    investigation_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    review_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # AI suggestion context
    ai_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_suggestion_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_disposition: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # accepted / edited / rejected / not_available

    # Case context snapshot (for similarity search later)
    case_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    case_priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    entity_industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    screening_match_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    alert_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship()
    user: Mapped["User"] = relationship()


class CaseMemoryEntry(Base, TimestampMixin):
    """Stores case context + embedding vector for similarity search.

    Each resolved case gets a memory entry that captures the full context
    so future similar cases can retrieve past decisions and reasoning.
    """
    __tablename__ = "case_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), unique=True, index=True)
    decision_capture_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("decision_captures.id"), nullable=True
    )

    # Searchable text representation
    summary_text: Mapped[str] = mapped_column(Text)
    # TF-IDF vector stored as JSON list of floats (lightweight, no external deps)
    embedding_vector: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Structured features for filtering
    case_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Tags for pattern grouping
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # e.g. ["high_risk", "screening_match", "sanctions"]

    # Relationships
    case: Mapped["Case"] = relationship()
    decision_capture: Mapped[Optional["DecisionCapture"]] = relationship()


class IntelligenceMetric(Base, TimestampMixin):
    """Time-series metrics for the decision intelligence dashboard.

    Stores computed metrics at regular intervals for trend visualization.
    """
    __tablename__ = "intelligence_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    metric_type: Mapped[str] = mapped_column(String(50), index=True)
    # decision_consistency, false_positive_trend, resolution_speed,
    # confidence_distribution, ai_usage, pattern_frequency
    metric_name: Mapped[str] = mapped_column(String(100))
    metric_value: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(20))  # daily, weekly, monthly, snapshot
    period_label: Mapped[str] = mapped_column(String(30))  # e.g. "2026-04-17", "2026-W16"
    breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # detailed sub-metrics


class CaseCluster(Base, TimestampMixin):
    """Groups of similar cases identified by the pattern detection engine."""
    __tablename__ = "case_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    cluster_name: Mapped[str] = mapped_column(String(255))
    cluster_type: Mapped[str] = mapped_column(String(50))
    # case_type_cluster, risk_cluster, decision_pattern, false_positive_cluster
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    case_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dominant_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    avg_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_resolution_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pattern_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    severity: Mapped[str] = mapped_column(String(20), default="low")
