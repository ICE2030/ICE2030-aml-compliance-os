"""Phase 5B: Compliance Snapshot model for risk trend tracking.

Stores point-in-time snapshots of compliance indicators so trends
can be visualized over time without fabricating history.
"""
from sqlalchemy import String, Integer, Float, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from typing import Optional
from datetime import datetime


class ComplianceSnapshot(Base, TimestampMixin):
    """Point-in-time snapshot of compliance state indicators.

    Each row captures a single metric at a specific moment.
    Trends are built by querying snapshots over time ranges.
    """
    __tablename__ = "compliance_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metric_key: Mapped[str] = mapped_column(String(100), index=True)
    # Metric keys:
    #   high_risk_obligations, unmapped_obligations, controls_without_evidence,
    #   expired_evidence, expiring_evidence, review_backlog,
    #   total_obligations, total_controls, total_evidence,
    #   avg_risk_score, control_coverage_pct, evidence_coverage_pct
    metric_value: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Optional breakdown by regulator, type, etc.
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CompliancePattern(Base, TimestampMixin):
    """Advanced pattern detection results linking obligations, controls,
    evidence gaps, and repeated high-risk areas.

    Each pattern is grounded in real stored data with full explainability.
    """
    __tablename__ = "compliance_patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    pattern_type: Mapped[str] = mapped_column(String(100), index=True)
    # Pattern types:
    #   control_risk_association — control types repeatedly linked to high-risk obligations
    #   persistent_evidence_gap — topics with chronic evidence gaps
    #   recurring_control_weakness — regulators/topics generating repeated failures
    #   obligation_type_risk_cluster — obligation types clustering at high risk
    #   regulator_risk_concentration — regulators with disproportionate high-risk items
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    # low, medium, high, critical
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # 0.0-1.0 — how strong the evidence for this pattern is
    affected_items: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # IDs of obligations, controls, evidence, regulators involved
    pattern_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Detailed breakdown: counts, percentages, supporting evidence
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_detected: Mapped[datetime] = mapped_column(DateTime(timezone=True))
