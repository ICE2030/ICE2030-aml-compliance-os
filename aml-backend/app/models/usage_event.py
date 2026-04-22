"""Lightweight usage event model — Phase V.

Tracks minimal user activity for usability analysis and demo telemetry.
Intentionally separate from Interaction (which captures rich decision context)
and GRCAuditTrail (which captures prev/new values on domain entities).

Stores only: who, what kind of event, where (path / resource), minimal metadata.
"""
from typing import Optional
from sqlalchemy import String, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class UsageEvent(Base, TimestampMixin):
    """A lightweight record of a user action or navigation event."""
    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )

    # event_type is one of: create, update, delete, navigate, demo_flow_view,
    # seed_load, export. Kept as a plain string to remain extensible without
    # schema migrations.
    event_type: Mapped[str] = mapped_column(String(50), index=True)

    # Target resource (nullable for navigation events)
    resource_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Frontend route for navigation events
    path: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Minimal structured metadata (title, filter, counts, etc.)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


Index("ix_usage_events_type_created", UsageEvent.event_type, UsageEvent.created_at)
