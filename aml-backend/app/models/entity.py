from sqlalchemy import String, Boolean, Text, Float, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
import enum
from typing import Optional, List


class EntityType(str, enum.Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class OnboardingStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_INFO = "requires_info"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"))
    entity_type: Mapped[EntityType] = mapped_column(SAEnum(EntityType))
    name: Mapped[str] = mapped_column(String(255))
    name_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    national_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    incorporation_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(10), default="SA")
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    onboarding_status: Mapped[OnboardingStatus] = mapped_column(
        SAEnum(OnboardingStatus), default=OnboardingStatus.DRAFT
    )
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(SAEnum(RiskLevel), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    additional_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="entities")
    ownership_links_as_parent: Mapped[List["OwnershipLink"]] = relationship(
        back_populates="parent_entity", foreign_keys="OwnershipLink.parent_entity_id"
    )
    ownership_links_as_child: Mapped[List["OwnershipLink"]] = relationship(
        back_populates="child_entity", foreign_keys="OwnershipLink.child_entity_id"
    )
    screening_results: Mapped[List["ScreeningResult"]] = relationship(back_populates="entity")
    cases: Mapped[List["Case"]] = relationship(back_populates="entity")
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="entity")
    documents: Mapped[List["Document"]] = relationship(back_populates="entity")


class OwnershipLink(Base, TimestampMixin):
    __tablename__ = "ownership_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    parent_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"))
    child_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"))
    ownership_percentage: Mapped[float] = mapped_column(Float)
    relationship_type: Mapped[str] = mapped_column(String(50), default="shareholder")
    is_ubo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_direct: Mapped[bool] = mapped_column(Boolean, default=True)

    parent_entity: Mapped["Entity"] = relationship(
        back_populates="ownership_links_as_parent", foreign_keys=[parent_entity_id]
    )
    child_entity: Mapped["Entity"] = relationship(
        back_populates="ownership_links_as_child", foreign_keys=[child_entity_id]
    )


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"))
    document_type: Mapped[str] = mapped_column(String(50))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    entity: Mapped["Entity"] = relationship(back_populates="documents")
