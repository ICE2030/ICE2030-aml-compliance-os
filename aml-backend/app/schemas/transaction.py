from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TransactionCreate(BaseModel):
    entity_id: str
    transaction_ref: str
    transaction_type: str
    amount: float
    currency: str = "SAR"
    counterparty_name: Optional[str] = None
    counterparty_country: Optional[str] = None
    description: Optional[str] = None
    transaction_date: str
    metadata: Optional[dict] = None


class TransactionResponse(BaseModel):
    id: str
    entity_id: str
    transaction_ref: str
    transaction_type: str
    amount: float
    currency: str
    counterparty_name: Optional[str] = None
    counterparty_country: Optional[str] = None
    description: Optional[str] = None
    transaction_date: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str  # threshold, velocity, pattern, country
    conditions: dict
    severity: str = "medium"
    is_active: bool = True


class TransactionRuleResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    rule_type: str
    conditions: dict
    severity: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionAlertResponse(BaseModel):
    id: str
    transaction_id: str
    rule_id: Optional[str] = None
    alert_type: str
    severity: str
    status: str
    description: str
    details: Optional[dict] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    case_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResolution(BaseModel):
    status: str  # dismissed, escalated, resolved
    resolution_note: str
    create_case: bool = False
