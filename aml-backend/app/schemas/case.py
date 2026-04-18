from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CaseCreate(BaseModel):
    entity_id: str
    case_type: str
    priority: str = "medium"
    title: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    sla_hours: Optional[int] = 48


class CaseUpdate(BaseModel):
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None


class CaseResponse(BaseModel):
    id: str
    case_number: str
    entity_id: str
    case_type: str
    priority: str
    status: str
    title: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    sla_breached: bool
    decision: Optional[str] = None
    decision_reasoning: Optional[str] = None
    decision_confidence: Optional[float] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    ai_summary: Optional[str] = None
    ai_suggestion: Optional[str] = None
    ai_suggestion_accepted: Optional[bool] = None
    time_to_decision_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseDecision(BaseModel):
    decision: str  # no_action, sar_filed, escalate, close_other
    reasoning: str
    confidence_level: float
    ai_suggestion_accepted: Optional[bool] = None


class CaseNoteCreate(BaseModel):
    content: str
    note_type: str = "comment"


class CaseNoteResponse(BaseModel):
    id: str
    case_id: str
    user_id: str
    content: str
    note_type: str
    created_at: datetime

    class Config:
        from_attributes = True
