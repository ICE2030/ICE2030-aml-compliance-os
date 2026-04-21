"""Enterprise Risk Management models.

Supports the full risk lifecycle:
- Risk identification and categorization
- Inherent and residual scoring
- Treatment strategy tracking
- Trend direction
- Links to obligations, controls, regulators
- Point-in-time risk snapshots
"""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class RiskCategoryEnum(str, enum.Enum):
    REGULATORY = "regulatory"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    FRAUD = "fraud"
    STRATEGIC = "strategic"
    FINANCIAL = "financial"
    TECHNOLOGY = "technology"
    THIRD_PARTY = "third_party"
    CONDUCT = "conduct"
    REPUTATIONAL = "reputational"


class LikelihoodLevel(str, enum.Enum):
    RARE = "rare"
    UNLIKELY = "unlikely"
    POSSIBLE = "possible"
    LIKELY = "likely"
    ALMOST_CERTAIN = "almost_certain"


class ImpactLevel(str, enum.Enum):
    INSIGNIFICANT = "insignificant"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


class TreatmentStrategy(str, enum.Enum):
    ACCEPT = "accept"
    MITIGATE = "mitigate"
    TRANSFER = "transfer"
    AVOID = "avoid"


class RiskStatus(str, enum.Enum):
    IDENTIFIED = "identified"
    ASSESSED = "assessed"
    TREATING = "treating"
    MONITORING = "monitoring"
    CLOSED = "closed"


class TrendDirection(str, enum.Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DETERIORATING = "deteriorating"
    NEW = "new"


class RiskCategory(Base, TimestampMixin):
    """Risk category / subcategory taxonomy."""
    __tablename__ = "grc_risk_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    category: Mapped[RiskCategoryEnum] = mapped_column(Enum(RiskCategoryEnum))
    subcategory: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subcategory_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    risks: Mapped[list["EnterpriseRisk"]] = relationship(back_populates="risk_category")


class EnterpriseRisk(Base, TimestampMixin):
    """Enterprise-level risk record with full lifecycle tracking."""
    __tablename__ = "grc_enterprise_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Identity
    title: Mapped[str] = mapped_column(String(500))
    title_ar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    category_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("grc_risk_categories.id"), nullable=True
    )
    category: Mapped[RiskCategoryEnum] = mapped_column(Enum(RiskCategoryEnum))
    subcategory: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Organizational context
    business_unit: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    business_unit_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    process: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    process_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Regulatory linkage (nullable — not all risks are regulation-linked)
    regulator_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regulators.id"), nullable=True
    )
    obligation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("obligations.id"), nullable=True
    )
    topic_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("topics.id"), nullable=True
    )

    # Root cause
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Inherent risk (before controls)
    inherent_likelihood: Mapped[LikelihoodLevel] = mapped_column(
        Enum(LikelihoodLevel), default=LikelihoodLevel.POSSIBLE
    )
    inherent_impact: Mapped[ImpactLevel] = mapped_column(
        Enum(ImpactLevel), default=ImpactLevel.MODERATE
    )
    inherent_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Control environment reference
    control_environment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_environment_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Residual risk (after controls)
    residual_likelihood: Mapped[LikelihoodLevel] = mapped_column(
        Enum(LikelihoodLevel), default=LikelihoodLevel.POSSIBLE
    )
    residual_impact: Mapped[ImpactLevel] = mapped_column(
        Enum(ImpactLevel), default=ImpactLevel.MODERATE
    )
    residual_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Treatment
    treatment_strategy: Mapped[TreatmentStrategy] = mapped_column(
        Enum(TreatmentStrategy), default=TreatmentStrategy.MITIGATE
    )
    treatment_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_plan_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership & status
    owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    owner_ar: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[RiskStatus] = mapped_column(
        Enum(RiskStatus), default=RiskStatus.IDENTIFIED
    )
    review_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trend_direction: Mapped[TrendDirection] = mapped_column(
        Enum(TrendDirection), default=TrendDirection.NEW
    )

    # Metadata
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    risk_category: Mapped[Optional["RiskCategory"]] = relationship(back_populates="risks")
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="risk", foreign_keys="Issue.risk_id"
    )


class RiskSnapshot(Base, TimestampMixin):
    """Point-in-time snapshot of a risk for trend tracking."""
    __tablename__ = "grc_risk_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    risk_id: Mapped[str] = mapped_column(ForeignKey("grc_enterprise_risks.id"))

    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    inherent_score: Mapped[float] = mapped_column(Float)
    residual_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50))
    trend_direction: Mapped[str] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
