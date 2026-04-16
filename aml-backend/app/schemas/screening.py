from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ScreeningRequest(BaseModel):
    entity_id: str
    screening_types: list[str] = ["sanctions", "pep"]


class ScreeningResultResponse(BaseModel):
    id: str
    entity_id: str
    screening_type: str
    matched_name: str
    match_score: float
    match_source: str
    match_details: Optional[dict] = None
    status: str
    resolved_by: Optional[str] = None
    resolution_reasoning: Optional[str] = None
    resolution_confidence: Optional[float] = None
    ai_suggestion: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_reasoning: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MatchResolution(BaseModel):
    status: str  # true_match, false_positive, inconclusive
    reasoning: str
    confidence_level: float
    ai_suggestion_accepted: Optional[bool] = None
