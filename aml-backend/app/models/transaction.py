from sqlalchemy import String, Float, Integer, Text, JSON, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
import enum
from typing import Optional, List
from datetime import datetime


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    ESCALATED = "escalated"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"))
    transaction_ref: Mapped[str] = mapped_column(String(100), unique=True)
    transaction_type: Mapped[str] = mapped_column(String(50))  # transfer, deposit, withdrawal, payment
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(5), default="SAR")
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    counterparty_country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[str] = mapped_column(String(30))
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    entity: Mapped["Entity"] = relationship(back_populates="transactions")
    alerts: Mapped[List["TransactionAlert"]] = relationship(back_populates="transaction")


class TransactionRule(Base, TimestampMixin):
    __tablename__ = "transaction_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(50))  # threshold, velocity, pattern, country
    conditions: Mapped[dict] = mapped_column(JSON)
    severity: Mapped[AlertSeverity] = mapped_column(SAEnum(AlertSeverity), default=AlertSeverity.MEDIUM)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="transaction_rules")


class TransactionAlert(Base, TimestampMixin):
    __tablename__ = "transaction_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"))
    rule_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("transaction_rules.id"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(50))  # rule_based, anomaly
    severity: Mapped[AlertSeverity] = mapped_column(SAEnum(AlertSeverity))
    status: Mapped[AlertStatus] = mapped_column(SAEnum(AlertStatus), default=AlertStatus.NEW)
    description: Mapped[str] = mapped_column(Text)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("cases.id"), nullable=True)

    transaction: Mapped["Transaction"] = relationship(back_populates="alerts")
    rule: Mapped[Optional["TransactionRule"]] = relationship()
    case: Mapped[Optional["Case"]] = relationship()
