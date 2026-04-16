from sqlalchemy import String, Float, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from typing import Optional


class Interaction(Base, TimestampMixin):
    """Captures ALL structured user interactions for reinforcing loops."""
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    # What happened
    interaction_type: Mapped[str] = mapped_column(String(50), index=True)
    # screening_resolution, case_decision, risk_override, ai_feedback, onboarding_review
    action: Mapped[str] = mapped_column(String(100))
    # Context
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str] = mapped_column(String(36))
    # Structured data
    decision: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_to_decision_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # AI context
    ai_suggestion_given: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_suggestion_accepted: Mapped[Optional[bool]] = mapped_column(nullable=True)
    ai_suggestion_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="interactions")


class LoopMetric(Base, TimestampMixin):
    """Stores computed metrics for the reinforcing loops."""
    __tablename__ = "loop_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    loop_type: Mapped[str] = mapped_column(String(50), index=True)
    # learning, trust, efficiency, compliance_strength
    metric_name: Mapped[str] = mapped_column(String(100))
    metric_value: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(20))  # daily, weekly, monthly
    period_start: Mapped[str] = mapped_column(String(30))
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class PatternDetection(Base, TimestampMixin):
    """Stores detected patterns across entities and cases."""
    __tablename__ = "pattern_detections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    pattern_type: Mapped[str] = mapped_column(String(50), index=True)
    # ownership_cluster, behavioral, geographic, temporal
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20))
    affected_entities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pattern_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
