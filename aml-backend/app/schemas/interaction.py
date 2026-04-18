from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InteractionCreate(BaseModel):
    interaction_type: str
    action: str
    resource_type: str
    resource_id: str
    decision: Optional[str] = None
    reasoning: Optional[str] = None
    confidence_level: Optional[float] = None
    time_to_decision_seconds: Optional[int] = None
    ai_suggestion_given: Optional[str] = None
    ai_suggestion_accepted: Optional[bool] = None
    ai_suggestion_feedback: Optional[str] = None
    metadata: Optional[dict] = None


class InteractionResponse(BaseModel):
    id: str
    user_id: str
    interaction_type: str
    action: str
    resource_type: str
    resource_id: str
    decision: Optional[str] = None
    reasoning: Optional[str] = None
    confidence_level: Optional[float] = None
    time_to_decision_seconds: Optional[int] = None
    ai_suggestion_given: Optional[str] = None
    ai_suggestion_accepted: Optional[bool] = None
    ai_suggestion_feedback: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LoopMetricResponse(BaseModel):
    id: str
    loop_type: str
    metric_name: str
    metric_value: float
    period: str
    period_start: str
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PatternDetectionResponse(BaseModel):
    id: str
    pattern_type: str
    title: str
    description: Optional[str] = None
    severity: str
    affected_entities: Optional[dict] = None
    pattern_data: Optional[dict] = None
    is_active: bool
    acknowledged_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardMetrics(BaseModel):
    total_entities: int
    total_cases: int
    open_cases: int
    pending_screenings: int
    high_risk_entities: int
    sla_breached_cases: int
    avg_resolution_time_hours: float
    false_positive_rate: float
    ai_acceptance_rate: float
    cases_by_status: dict
    cases_by_priority: dict
    risk_distribution: dict
    loop_metrics: dict
