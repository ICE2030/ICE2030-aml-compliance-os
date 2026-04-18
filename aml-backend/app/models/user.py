from sqlalchemy import String, Boolean, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
import enum
from typing import Optional, List


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    COMPLIANCE_OFFICER = "compliance_officer"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.ANALYST)
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")

    organization: Mapped[Optional["Organization"]] = relationship(back_populates="users")
    assigned_cases: Mapped[List["Case"]] = relationship(
        back_populates="assigned_to_user", foreign_keys="Case.assigned_to"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")
    interactions: Mapped[List["Interaction"]] = relationship(back_populates="user")


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255))
    name_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    org_type: Mapped[str] = mapped_column(String(50), default="fintech")
    country: Mapped[str] = mapped_column(String(10), default="SA")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[List["User"]] = relationship(back_populates="organization")
    entities: Mapped[List["Entity"]] = relationship(back_populates="organization")
    risk_rules: Mapped[List["RiskRule"]] = relationship(back_populates="organization")
    transaction_rules: Mapped[List["TransactionRule"]] = relationship(back_populates="organization")
