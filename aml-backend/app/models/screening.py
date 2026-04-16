from sqlalchemy import String, Float, Text, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
import enum
from typing import Optional, List


class ScreeningType(str, enum.Enum):
    SANCTIONS = "sanctions"
    PEP = "pep"
    ADVERSE_MEDIA = "adverse_media"


class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    TRUE_MATCH = "true_match"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"


class ScreeningResult(Base, TimestampMixin):
    __tablename__ = "screening_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id"))
    screening_type: Mapped[ScreeningType] = mapped_column(SAEnum(ScreeningType))
    # Match details
    matched_name: Mapped[str] = mapped_column(String(255))
    match_score: Mapped[float] = mapped_column(Float)
    match_source: Mapped[str] = mapped_column(String(100))
    match_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Resolution
    status: Mapped[MatchStatus] = mapped_column(SAEnum(MatchStatus), default=MatchStatus.PENDING)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolution_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # AI suggestion
    ai_suggestion: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    entity: Mapped["Entity"] = relationship(back_populates="screening_results")
    resolver: Mapped[Optional["User"]] = relationship(foreign_keys=[resolved_by])
