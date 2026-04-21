"""Phase R: Regulatory Data Maturity Layer models.

1. ProvisionSnapshot — before/after snapshots for change detection
2. RegulatoryChange — detected changes with classification
3. ImpactRecord — propagated impacts on obligations/controls/evidence/risks
4. RegulatoryAlert — triggered alerts for high-impact changes
5. RegulatorFreshness — confidence & freshness tracking per regulator
"""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════

class ChangeClassification(str, enum.Enum):
    """How a regulatory change should be classified."""
    INFORMATIONAL = "informational"   # cosmetic / formatting / metadata
    INTERPRETIVE = "interpretive"     # clarification / rewording without new obligation
    OPERATIONAL = "operational"       # new process / reporting / deadline change
    MATERIAL = "material"             # new obligation / penalty / prohibition change


class ChangeScope(str, enum.Enum):
    """What entity was changed."""
    DOCUMENT_NEW = "document_new"
    DOCUMENT_UPDATED = "document_updated"
    PROVISION_ADDED = "provision_added"
    PROVISION_MODIFIED = "provision_modified"
    PROVISION_REMOVED = "provision_removed"
    OBLIGATION_ADDED = "obligation_added"
    OBLIGATION_MODIFIED = "obligation_modified"
    OBLIGATION_REMOVED = "obligation_removed"


class ImpactType(str, enum.Enum):
    """What type of record is impacted."""
    OBLIGATION = "obligation"
    CONTROL = "control"
    EVIDENCE = "evidence"
    RISK = "risk"
    ACTION = "action"


class ImpactStatus(str, enum.Enum):
    """Status of the impact review."""
    REQUIRES_REVIEW = "requires_review"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"
    ACTION_TAKEN = "action_taken"


class AlertSeverity(str, enum.Enum):
    """Severity of regulatory alert."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    """Status of the alert."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FreshnessStatus(str, enum.Enum):
    """How fresh the regulatory data is."""
    CURRENT = "current"         # updated within expected window
    AGING = "aging"             # approaching staleness
    STALE = "stale"             # overdue for update
    UNKNOWN = "unknown"         # never updated / no baseline


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Provision Snapshots (before/after for change detection)
# ═══════════════════════════════════════════════════════════════════════════════

class ProvisionSnapshot(Base, TimestampMixin):
    """Point-in-time snapshot of a provision for version comparison."""
    __tablename__ = "provision_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    provision_id: Mapped[str] = mapped_column(ForeignKey("provisions.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("regulatory_documents.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1)

    # Snapshot content (frozen at point in time)
    section_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    text_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provision_type: Mapped[str] = mapped_column(String(50))
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256

    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot_reason: Mapped[str] = mapped_column(String(100), default="initial_import")
    # "initial_import", "change_detected", "manual_snapshot"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Regulatory Changes (detected changes with classification)
# ═══════════════════════════════════════════════════════════════════════════════

class RegulatoryChange(Base, TimestampMixin):
    """A detected regulatory change with before/after and classification."""
    __tablename__ = "regulatory_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # What changed
    document_id: Mapped[str] = mapped_column(ForeignKey("regulatory_documents.id"))
    provision_id: Mapped[Optional[str]] = mapped_column(ForeignKey("provisions.id"), nullable=True)
    regulator_id: Mapped[str] = mapped_column(ForeignKey("regulators.id"))

    # Change scope and classification
    change_scope: Mapped[ChangeScope] = mapped_column(Enum(ChangeScope))
    classification: Mapped[ChangeClassification] = mapped_column(
        Enum(ChangeClassification), default=ChangeClassification.INFORMATIONAL
    )

    # Before / After snapshots
    before_snapshot_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("provision_snapshots.id"), nullable=True
    )
    after_snapshot_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("provision_snapshots.id"), nullable=True
    )

    # Summaries
    summary: Mapped[str] = mapped_column(Text)
    summary_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_sections: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Detection metadata
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detection_method: Mapped[str] = mapped_column(String(50), default="content_hash")
    # "content_hash", "text_diff", "manual"

    # Review
    review_status: Mapped[str] = mapped_column(String(50), default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Impact Records (propagated impacts on downstream records)
# ═══════════════════════════════════════════════════════════════════════════════

class ImpactRecord(Base, TimestampMixin):
    """Records impact of a regulatory change on downstream entities."""
    __tablename__ = "impact_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    change_id: Mapped[str] = mapped_column(ForeignKey("regulatory_changes.id"))

    # What is impacted
    impact_type: Mapped[ImpactType] = mapped_column(Enum(ImpactType))
    impacted_record_id: Mapped[str] = mapped_column(String(36))  # FK to obligation/control/evidence/risk/action
    impacted_record_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Impact details
    impact_description: Mapped[str] = mapped_column(Text)
    impact_description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_action_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[ImpactStatus] = mapped_column(
        Enum(ImpactStatus), default=ImpactStatus.REQUIRES_REVIEW
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Regulatory Alerts
# ═══════════════════════════════════════════════════════════════════════════════

class RegulatoryAlert(Base, TimestampMixin):
    """Alert triggered by high-impact regulatory changes."""
    __tablename__ = "regulatory_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    change_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regulatory_changes.id"), nullable=True
    )
    regulator_id: Mapped[str] = mapped_column(ForeignKey("regulators.id"))

    # Alert details
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity))
    alert_type: Mapped[str] = mapped_column(String(100))
    # "new_binding_obligation", "material_change", "high_impact_change",
    # "obligation_removed", "penalty_change", "freshness_degraded"

    # Affected counts
    affected_obligations_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_controls_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_evidence_count: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.ACTIVE
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Regulator Freshness Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class RegulatorFreshness(Base, TimestampMixin):
    """Tracks data freshness and confidence per regulator."""
    __tablename__ = "regulator_freshness"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    regulator_id: Mapped[str] = mapped_column(ForeignKey("regulators.id"), unique=True)

    # Timestamps
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_change_detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Freshness
    freshness_status: Mapped[FreshnessStatus] = mapped_column(
        Enum(FreshnessStatus), default=FreshnessStatus.UNKNOWN
    )
    expected_update_frequency_days: Mapped[int] = mapped_column(Integer, default=30)
    days_since_last_update: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Confidence
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 - 1.0
    confidence_degradation_rate: Mapped[float] = mapped_column(Float, default=0.01)
    # per day past expected update window

    # Stats
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    total_provisions: Mapped[int] = mapped_column(Integer, default=0)
    total_obligations: Mapped[int] = mapped_column(Integer, default=0)
    total_changes_detected: Mapped[int] = mapped_column(Integer, default=0)
    total_pending_reviews: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
