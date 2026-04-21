from sqlalchemy import String, Float, Integer, Text, JSON, ForeignKey, Enum as SAEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
import enum
from typing import Optional, List
from datetime import datetime


class CasePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    UNDER_INVESTIGATION = "under_investigation"
    PENDING_DECISION = "pending_decision"
    ESCALATED = "escalated"
    CLOSED_NO_ACTION = "closed_no_action"
    CLOSED_SAR_FILED = "closed_sar_filed"
    CLOSED_OTHER = "closed_other"


class CaseType(str, enum.Enum):
    SCREENING_MATCH = "screening_match"
    TRANSACTION_ALERT = "transaction_alert"
    MANUAL_REFERRAL = "manual_referral"
    PERIODIC_REVIEW = "periodic_review"
    RISK_ESCALATION = "risk_escalation"
    AML_REVIEW = "aml_review"
    CDD_REVIEW = "cdd_review"
    SANCTIONS_REVIEW = "sanctions_review"
    STR_FILING = "str_filing"


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    case_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"))
    case_type: Mapped[CaseType] = mapped_column(SAEnum(CaseType))
    priority: Mapped[CasePriority] = mapped_column(SAEnum(CasePriority), default=CasePriority.MEDIUM)
    status: Mapped[CaseStatus] = mapped_column(SAEnum(CaseStatus), default=CaseStatus.OPEN)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Assignment
    assigned_to: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    # SLA
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_breached: Mapped[bool] = mapped_column(default=False)
    # Decision
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decision_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # AI
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_suggestion_accepted: Mapped[Optional[bool]] = mapped_column(nullable=True)
    # Metrics
    time_to_decision_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    entity: Mapped["Entity"] = relationship(back_populates="cases")
    assigned_to_user: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_cases", foreign_keys=[assigned_to]
    )
    decided_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[decided_by])
    notes: Mapped[List["CaseNote"]] = relationship(back_populates="case")


class CaseNote(Base, TimestampMixin):
    __tablename__ = "case_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    note_type: Mapped[str] = mapped_column(String(30), default="comment")  # comment, decision, escalation
    attachments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    case: Mapped["Case"] = relationship(back_populates="notes")
    user: Mapped["User"] = relationship()
