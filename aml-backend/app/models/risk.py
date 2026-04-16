from sqlalchemy import String, Float, Integer, Text, JSON, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
import enum
from typing import Optional, List
from datetime import datetime


class RiskRule(Base, TimestampMixin):
    __tablename__ = "risk_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50))  # country, industry, product, behavior
    # Rule definition
    field: Mapped[str] = mapped_column(String(100))  # field to evaluate
    operator: Mapped[str] = mapped_column(String(20))  # eq, neq, in, contains, gt, lt
    value: Mapped[str] = mapped_column(Text)  # value to compare (JSON encoded for lists)
    score_impact: Mapped[float] = mapped_column(Float)  # points to add if matched
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="risk_rules")


class RiskAssessment(Base, TimestampMixin):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"))
    assessed_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    # Scoring
    total_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(20))
    matched_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # list of matched rule details
    # Override
    is_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    override_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    override_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
