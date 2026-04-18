"""Phase 3: Decision Intelligence schemas."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- Decision Capture ---

class DecisionCaptureCreate(BaseModel):
    """Input for structured case decision capture."""
    decision: str  # approve / reject / escalate / sar_filed / no_action
    reasoning_text: str
    reasoning_categories: Optional[dict] = None
    user_confidence: float = Field(ge=0, le=1)
    investigation_time_seconds: Optional[int] = None
    review_time_seconds: Optional[int] = None
    ai_disposition: Optional[str] = None  # accepted / edited / rejected / not_available


class DecisionCaptureResponse(BaseModel):
    id: str
    case_id: str
    user_id: str
    decision: str
    reasoning_text: str
    reasoning_categories: Optional[dict] = None
    user_confidence: float
    time_to_decision_seconds: Optional[int] = None
    investigation_time_seconds: Optional[int] = None
    review_time_seconds: Optional[int] = None
    ai_suggestion: Optional[str] = None
    ai_suggestion_confidence: Optional[float] = None
    ai_disposition: Optional[str] = None
    case_type: Optional[str] = None
    case_priority: Optional[str] = None
    entity_type: Optional[str] = None
    entity_risk_level: Optional[str] = None
    entity_industry: Optional[str] = None
    entity_country: Optional[str] = None
    screening_match_count: Optional[int] = None
    alert_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Case Memory / Similarity ---

class SimilarCaseResult(BaseModel):
    case_id: str
    case_number: str
    title: str
    case_type: str
    decision: Optional[str] = None
    reasoning: Optional[str] = None
    entity_name: Optional[str] = None
    risk_level: Optional[str] = None
    similarity_score: float
    similarity_method: str  # semantic / structured / hybrid
    time_to_decision_minutes: Optional[int] = None
    user_confidence: Optional[float] = None


class CaseMemoryResponse(BaseModel):
    case_id: str
    summary_text: str
    case_type: Optional[str] = None
    decision: Optional[str] = None
    entity_type: Optional[str] = None
    risk_level: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    tags: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Intelligence Metrics ---

class LoopInstrumentationResponse(BaseModel):
    """All loop metrics in one response."""
    decision_loop: dict
    false_positive_loop: dict
    efficiency_loop: dict
    trust_loop: dict
    computed_at: datetime


class IntelligenceMetricResponse(BaseModel):
    id: str
    metric_type: str
    metric_name: str
    metric_value: float
    period: str
    period_label: str
    breakdown: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Pattern Detection ---

class CaseClusterResponse(BaseModel):
    id: str
    cluster_name: str
    cluster_type: str
    description: Optional[str] = None
    case_count: int
    dominant_decision: Optional[str] = None
    avg_confidence: Optional[float] = None
    avg_resolution_seconds: Optional[int] = None
    pattern_data: Optional[dict] = None
    is_active: bool
    severity: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Outcome Dashboard ---

class OutcomeDashboardResponse(BaseModel):
    """Comprehensive intelligence dashboard data."""
    # Decision consistency
    decision_distribution: dict  # {decision_type: count}
    decision_consistency_score: float  # 0-1
    avg_confidence: float
    confidence_distribution: dict  # {bucket: count}

    # False positive trends
    false_positive_rate: float
    false_positive_trend: list  # [{period, rate}]
    alert_dismissed_ratio: float

    # Resolution speed
    avg_resolution_minutes: float
    resolution_trend: list  # [{period, avg_minutes}]
    resolution_by_type: dict  # {case_type: avg_minutes}

    # AI usage metrics
    ai_acceptance_rate: float
    ai_override_rate: float
    ai_disposition_breakdown: dict  # {accepted: n, edited: n, rejected: n}
    ai_suggestion_accuracy: float

    # Pattern summary
    active_clusters: int
    top_patterns: list  # [{name, count, severity}]
    recurring_false_positives: int

    # Loop health
    loop_health: dict
