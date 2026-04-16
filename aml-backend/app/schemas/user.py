from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "analyst"
    organization_id: Optional[str] = None
    preferred_language: str = "en"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    preferred_language: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: Optional[str] = None
    is_active: bool
    preferred_language: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LoginRequest(BaseModel):
    email: str
    password: str


class OrganizationCreate(BaseModel):
    name: str
    name_ar: Optional[str] = None
    license_number: Optional[str] = None
    org_type: str = "fintech"
    country: str = "SA"


class OrganizationResponse(BaseModel):
    id: str
    name: str
    name_ar: Optional[str] = None
    license_number: Optional[str] = None
    org_type: str
    country: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
