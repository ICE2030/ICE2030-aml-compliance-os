from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class EntityCreate(BaseModel):
    entity_type: str  # individual, company
    name: str
    name_ar: Optional[str] = None
    national_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    registration_number: Optional[str] = None
    license_number: Optional[str] = None
    incorporation_date: Optional[str] = None
    industry: Optional[str] = None
    country: str = "SA"
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    additional_data: Optional[dict] = None


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    onboarding_status: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    additional_data: Optional[dict] = None


class EntityResponse(BaseModel):
    id: str
    organization_id: str
    entity_type: str
    name: str
    name_ar: Optional[str] = None
    national_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    registration_number: Optional[str] = None
    license_number: Optional[str] = None
    incorporation_date: Optional[str] = None
    industry: Optional[str] = None
    country: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    onboarding_status: str
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    risk_factors: Optional[dict] = None
    additional_data: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OwnershipLinkCreate(BaseModel):
    parent_entity_id: str
    child_entity_id: str
    ownership_percentage: float
    relationship_type: str = "shareholder"
    is_ubo: bool = False
    is_direct: bool = True


class OwnershipLinkResponse(BaseModel):
    id: str
    parent_entity_id: str
    child_entity_id: str
    ownership_percentage: float
    relationship_type: str
    is_ubo: bool
    is_direct: bool
    created_at: datetime

    class Config:
        from_attributes = True


class OnboardingAction(BaseModel):
    action: str  # approve, reject, request_info
    reasoning: str
    confidence_level: float = 0.8
