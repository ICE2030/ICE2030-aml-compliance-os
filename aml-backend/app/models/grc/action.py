"""Unified Action model — Phase G3.

Every action is linked to exactly one source entity (risk, issue, finding,
obligation, control, or evidence). Actions can be system-generated (from
patterns, alerts) or manually created.

Supports:
- Unified action tracking across the entire GRC platform
- Priority-based filtering and overdue detection
- Pattern-to-action bridge (generated → approved workflow)
- Alert-to-action conversion
- Full bilingual support (EN + AR)
"""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


# ── Enums ──

class ActionPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class ActionSourceType(str, enum.Enum):
    RISK = "risk"
    ISSUE = "issue"
    AUDIT_FINDING = "audit_finding"
    OBLIGATION = "obligation"
    CONTROL = "control"
    EVIDENCE = "evidence"
    PATTERN = "pattern"
    ALERT = "alert"
    MANUAL = "manual"


class ActionOrigin(str, enum.Enum):
    MANUAL = "manual"
    PATTERN_GENERATED = "pattern_generated"
    ALERT_GENERATED = "alert_generated"
    DASHBOARD_GENERATED = "dashboard_generated"


# ── Models ──

class GRCAction(Base, TimestampMixin):
    """A unified action item linked to any GRC entity."""
    __tablename__ = "grc_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Description
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Why this action is needed
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source linkage — polymorphic reference
    source_type: Mapped[ActionSourceType] = mapped_column(
        Enum(ActionSourceType), default=ActionSourceType.MANUAL
    )
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Origin — how the action was created
    origin: Mapped[ActionOrigin] = mapped_column(
        Enum(ActionOrigin), default=ActionOrigin.MANUAL
    )

    # Classification
    priority: Mapped[ActionPriority] = mapped_column(
        Enum(ActionPriority), default=ActionPriority.MEDIUM
    )
    status: Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus), default=ActionStatus.OPEN
    )

    # Ownership & deadlines
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cross-linking — additional related entities
    linked_risk_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    linked_issue_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    linked_finding_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    linked_obligation_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    linked_control_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    linked_evidence_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Resolution
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_notes_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class NarrativeSummary(Base, TimestampMixin):
    """AI-generated narrative summary — clearly marked, editable, not authoritative."""
    __tablename__ = "grc_narrative_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Type of narrative
    narrative_type: Mapped[str] = mapped_column(String(100))  # executive, risk, audit, exposure, action_rationale

    # Content — clearly marked as AI-generated
    content: Mapped[str] = mapped_column(Text)
    content_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Edit tracking
    is_edited: Mapped[bool] = mapped_column(default=False)
    edited_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Provenance
    generated_from: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # snapshot of data used
    ai_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="rule-based")
    confidence_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
