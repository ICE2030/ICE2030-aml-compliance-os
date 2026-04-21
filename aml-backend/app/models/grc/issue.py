"""Issue Management & Remediation models.

Issues can originate from:
- audit findings
- risk assessments
- compliance gaps
- incidents
- management reviews
- regulator notes

Remediation actions track resolution with milestones, progress, and closure validation.
"""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class IssueSource(str, enum.Enum):
    AUDIT = "audit"
    RISK = "risk"
    COMPLIANCE = "compliance"
    INCIDENT = "incident"
    MANAGEMENT_REVIEW = "management_review"
    REGULATOR_NOTE = "regulator_note"


class IssueSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_CLOSURE = "pending_closure"
    CLOSED = "closed"
    OVERDUE = "overdue"
    ESCALATED = "escalated"


class EscalationStatus(str, enum.Enum):
    NONE = "none"
    ESCALATED_L1 = "escalated_l1"
    ESCALATED_L2 = "escalated_l2"
    ESCALATED_BOARD = "escalated_board"


class RemediationStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    VERIFIED = "verified"


class Issue(Base, TimestampMixin):
    """A compliance, risk, or audit issue requiring resolution."""
    __tablename__ = "grc_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Identity
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source & classification
    source: Mapped[IssueSource] = mapped_column(Enum(IssueSource))
    severity: Mapped[IssueSeverity] = mapped_column(Enum(IssueSeverity), default=IssueSeverity.MEDIUM)
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus), default=IssueStatus.OPEN)
    escalation_status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus), default=EscalationStatus.NONE
    )

    # Linkages (all nullable — issues can be linked to multiple entity types)
    risk_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("grc_enterprise_risks.id"), nullable=True
    )
    control_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("controls.id"), nullable=True
    )
    obligation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("obligations.id"), nullable=True
    )
    regulator_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regulators.id"), nullable=True
    )

    # Ownership & deadlines
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Closure validation
    closure_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closure_validated_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    closure_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    risk: Mapped[Optional["EnterpriseRisk"]] = relationship(
        back_populates="issues", foreign_keys=[risk_id]
    )
    remediation_actions: Mapped[list["RemediationAction"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


class RemediationAction(Base, TimestampMixin):
    """An action plan to resolve an issue."""
    __tablename__ = "grc_remediation_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    issue_id: Mapped[str] = mapped_column(ForeignKey("grc_issues.id"))

    # Action details
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership & scheduling
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Progress
    status: Mapped[RemediationStatus] = mapped_column(
        Enum(RemediationStatus), default=RemediationStatus.NOT_STARTED
    )
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    blockers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Closure
    closure_test: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effectiveness_check: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    issue: Mapped["Issue"] = relationship(back_populates="remediation_actions")
    milestones: Mapped[list["ActionMilestone"]] = relationship(back_populates="action", cascade="all, delete-orphan")


class ActionMilestone(Base, TimestampMixin):
    """A milestone within a remediation action."""
    __tablename__ = "grc_action_milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    action_id: Mapped[str] = mapped_column(ForeignKey("grc_remediation_actions.id"))

    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    action: Mapped["RemediationAction"] = relationship(back_populates="milestones")
