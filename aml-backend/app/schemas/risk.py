from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RiskRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str  # country, industry, product, behavior
    field: str
    operator: str  # eq, neq, in, contains, gt, lt
    value: str
    score_impact: float
    weight: float = 1.0
    is_active: bool = True


class RiskRuleResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    category: str
    field: str
    operator: str
    value: str
    score_impact: float
    weight: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RiskAssessmentResponse(BaseModel):
    id: str
    entity_id: str
    assessed_by: Optional[str] = None
    total_score: float
    risk_level: str
    matched_rules: Optional[dict] = None
    is_overridden: bool
    override_level: Optional[str] = None
    override_reasoning: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RiskOverride(BaseModel):
    override_level: str  # low, medium, high, critical
    reasoning: str
    confidence_level: float
