from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime
    entry_hash: Optional[str] = None

    class Config:
        from_attributes = True


class AuditExportRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    resource_type: Optional[str] = None
    action: Optional[str] = None
