"""Internal Audit models — Phase G2.

AuditPlan → AuditEngagement → ControlTest → AuditFinding → ManagementResponse

Supports:
- Audit planning with risk-based scope
- Engagement execution with linkage to controls, risks, obligations
- Design and operating effectiveness testing
- Findings with severity, root cause, impacted controls
- Management responses with remediation linkage
- Full bilingual support (EN + AR)
"""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


# ── Enums ──

class AuditPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EngagementStatus(str, enum.Enum):
    PLANNED = "planned"
    FIELDWORK = "fieldwork"
    REPORTING = "reporting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestResult(str, enum.Enum):
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"
    NOT_TESTED = "not_tested"


class TestType(str, enum.Enum):
    DESIGN = "design"
    OPERATING = "operating"
    BOTH = "both"


class FindingSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    IN_REMEDIATION = "in_remediation"
    PENDING_CLOSURE = "pending_closure"
    CLOSED = "closed"


class ResponseStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


# ── Models ──

class AuditPlan(Base, TimestampMixin):
    """An audit plan covering a specific period and scope."""
    __tablename__ = "grc_audit_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Identity
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Period
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scope
    scope_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_summary_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Linkages (nullable — plans can be scoped to specific areas)
    risk_categories: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # list of category strings
    regulator_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # list of regulator IDs
    topic_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # list of topic IDs
    business_units: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # list of BU strings
    processes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # list of process strings

    # Ownership & status
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[AuditPlanStatus] = mapped_column(
        Enum(AuditPlanStatus), default=AuditPlanStatus.DRAFT
    )

    # Relationships
    engagements: Mapped[list["AuditEngagement"]] = relationship(
        back_populates="audit_plan", cascade="all, delete-orphan"
    )


class AuditEngagement(Base, TimestampMixin):
    """An audit engagement — a specific audit within a plan."""
    __tablename__ = "grc_audit_engagements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    plan_id: Mapped[str] = mapped_column(ForeignKey("grc_audit_plans.id"))

    # Identity
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scope & objectives
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objectives: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objectives_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Schedule
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Linkages for risk-based audit planning
    risk_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # linked enterprise risk IDs
    control_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # linked control IDs
    obligation_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # linked obligation IDs
    evidence_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # linked evidence IDs

    # Ownership & status
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[EngagementStatus] = mapped_column(
        Enum(EngagementStatus), default=EngagementStatus.PLANNED
    )

    # Metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    audit_plan: Mapped["AuditPlan"] = relationship(back_populates="engagements")
    control_tests: Mapped[list["ControlTest"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    findings: Mapped[list["AuditFinding"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )


class ControlTest(Base, TimestampMixin):
    """A control test — design or operating effectiveness."""
    __tablename__ = "grc_control_tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("grc_audit_engagements.id"))

    # Tested control
    control_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("controls.id"), nullable=True
    )

    # Test details
    test_type: Mapped[TestType] = mapped_column(Enum(TestType), default=TestType.BOTH)
    procedure: Mapped[str] = mapped_column(Text)
    procedure_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Execution
    tester: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tester_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    test_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Results
    design_result: Mapped[TestResult] = mapped_column(
        Enum(TestResult), default=TestResult.NOT_TESTED
    )
    operating_result: Mapped[TestResult] = mapped_column(
        Enum(TestResult), default=TestResult.NOT_TESTED
    )
    overall_result: Mapped[TestResult] = mapped_column(
        Enum(TestResult), default=TestResult.NOT_TESTED
    )

    # Notes & evidence
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Sample details
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exceptions_found: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    engagement: Mapped["AuditEngagement"] = relationship(back_populates="control_tests")


class AuditFinding(Base, TimestampMixin):
    """An audit finding — a specific deficiency discovered during an engagement."""
    __tablename__ = "grc_audit_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("grc_audit_engagements.id"))

    # Identity
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity), default=FindingSeverity.MEDIUM
    )
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus), default=FindingStatus.OPEN
    )

    # Root cause
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Linkages
    control_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # impacted control IDs
    risk_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # linked risk IDs
    obligation_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # linked obligation IDs
    evidence_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # linked evidence IDs

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
    engagement: Mapped["AuditEngagement"] = relationship(back_populates="findings")
    management_responses: Mapped[list["ManagementResponse"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class ManagementResponse(Base, TimestampMixin):
    """A management response to an audit finding."""
    __tablename__ = "grc_management_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    finding_id: Mapped[str] = mapped_column(ForeignKey("grc_audit_findings.id"))

    # Response
    response_text: Mapped[str] = mapped_column(Text)
    response_text_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership & deadlines
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    status: Mapped[ResponseStatus] = mapped_column(
        Enum(ResponseStatus), default=ResponseStatus.PENDING
    )

    # Remediation linkage (nullable — not all responses create remediation actions)
    remediation_action_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("grc_remediation_actions.id"), nullable=True
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    finding: Mapped["AuditFinding"] = relationship(back_populates="management_responses")
