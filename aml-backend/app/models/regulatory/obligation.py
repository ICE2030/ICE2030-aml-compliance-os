"""Obligation, Control, Evidence, and Risk models."""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class ObligationType(str, enum.Enum):
    MANDATORY = "mandatory"
    PROHIBITION = "prohibition"
    REPORTING = "reporting"
    DEADLINE = "deadline"
    THRESHOLD = "threshold"
    GOVERNANCE = "governance"
    RECORDKEEPING = "recordkeeping"
    PENALTY = "penalty"
    DEFINITION = "definition"
    IDENTIFICATION = "identification"
    VERIFICATION = "verification"
    ONGOING_MONITORING = "ongoing_monitoring"


class ExtractionMethod(str, enum.Enum):
    RULE_BASED = "rule_based"
    AI_EXTRACTED = "ai_extracted"
    MANUAL = "manual"
    HYBRID = "hybrid"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class ControlType(str, enum.Enum):
    POLICY = "policy"
    PROCEDURE = "procedure"
    TECHNICAL = "technical"
    MONITORING = "monitoring"
    TRAINING = "training"


class ControlStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"


class EvidenceType(str, enum.Enum):
    DOCUMENT = "document"
    LOG = "log"
    ATTESTATION = "attestation"
    REPORT = "report"
    SCREENSHOT = "screenshot"
    CERTIFICATE = "certificate"
    POLICY_DOC = "policy_doc"
    TRAINING_RECORD = "training_record"
    SYSTEM_OUTPUT = "system_output"


class EvidenceStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    UNDER_REVIEW = "under_review"
    ARCHIVED = "archived"


class CollectionMethod(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    SEMI_AUTOMATED = "semi_automated"
    SYSTEM_GENERATED = "system_generated"


class RiskSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLikelihood(str, enum.Enum):
    UNLIKELY = "unlikely"
    POSSIBLE = "possible"
    LIKELY = "likely"
    ALMOST_CERTAIN = "almost_certain"


class RiskType(str, enum.Enum):
    REGULATORY = "regulatory"
    FINANCIAL = "financial"
    REPUTATIONAL = "reputational"
    OPERATIONAL = "operational"


class ActionType(str, enum.Enum):
    FILING = "filing"
    REMEDIATION = "remediation"
    TRAINING = "training"
    POLICY_UPDATE = "policy_update"
    CONTROL_ENHANCEMENT = "control_enhancement"
    INVESTIGATION = "investigation"


class ActionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class Obligation(Base, TimestampMixin):
    __tablename__ = "obligations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    provision_id: Mapped[str] = mapped_column(ForeignKey("provisions.id"))
    text: Mapped[str] = mapped_column(Text)
    text_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_summary_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    obligation_type: Mapped[ObligationType] = mapped_column(Enum(ObligationType))
    applies_to_entity_types: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # ["bank", "fintech", "insurance"]
    applies_to_product_types: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(Enum(ExtractionMethod), default=ExtractionMethod.RULE_BASED)
    review_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase 4: criticality level for risk scoring
    criticality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # low, medium, high, critical

    controls: Mapped[list["ObligationControl"]] = relationship(back_populates="obligation")
    risks: Mapped[list["RegulatoryRisk"]] = relationship(back_populates="obligation")
    actions: Mapped[list["RegulatoryAction"]] = relationship(back_populates="obligation")


class Control(Base, TimestampMixin):
    __tablename__ = "controls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(300))
    name_ar: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_type: Mapped[ControlType] = mapped_column(Enum(ControlType))
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[ControlStatus] = mapped_column(Enum(ControlStatus), default=ControlStatus.DRAFT)
    frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # daily, weekly, monthly, quarterly, annual, continuous
    effectiveness_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.0-1.0
    last_tested: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    test_frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Phase 4: regulator/source context
    regulator_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    seed_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, unique=True)

    obligations: Mapped[list["ObligationControl"]] = relationship(back_populates="control")
    evidence: Mapped[list["EvidenceArtifact"]] = relationship(back_populates="control")


class ObligationControl(Base, TimestampMixin):
    __tablename__ = "obligation_controls"

    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.id"), primary_key=True)
    control_id: Mapped[str] = mapped_column(ForeignKey("controls.id"), primary_key=True)
    mapping_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    mapping_method: Mapped[str] = mapped_column(String(50), default="manual")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    obligation: Mapped["Obligation"] = relationship(back_populates="controls")
    control: Mapped["Control"] = relationship(back_populates="obligations")


class EvidenceArtifact(Base, TimestampMixin):
    __tablename__ = "evidence_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    control_id: Mapped[str] = mapped_column(ForeignKey("controls.id"))
    name: Mapped[str] = mapped_column(String(300), default="")
    name_ar: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(100))  # document, log, attestation, report, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_system: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # where evidence comes from
    collection_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # manual, automated, etc.
    periodicity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # daily, weekly, monthly, etc.
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    seed_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, unique=True)

    control: Mapped["Control"] = relationship(back_populates="evidence")


class RegulatoryRisk(Base, TimestampMixin):
    __tablename__ = "regulatory_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.id"))
    risk_type: Mapped[RiskType] = mapped_column(Enum(RiskType))
    severity: Mapped[str] = mapped_column(String(50))  # low, medium, high, critical
    likelihood: Mapped[str] = mapped_column(String(50))  # unlikely, possible, likely, almost_certain
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # composite 0.0-1.0
    mitigation_status: Mapped[str] = mapped_column(String(50), default="unmitigated")
    penalty_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # transparent breakdown

    obligation: Mapped["Obligation"] = relationship(back_populates="risks")


class RegulatoryAction(Base, TimestampMixin):
    __tablename__ = "regulatory_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.id"))
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType))
    description: Mapped[str] = mapped_column(Text)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ActionStatus] = mapped_column(Enum(ActionStatus), default=ActionStatus.OPEN)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    obligation: Mapped["Obligation"] = relationship(back_populates="actions")
