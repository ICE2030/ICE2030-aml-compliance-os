from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import verify_password, get_password_hash, create_access_token, get_current_user
from app.models.user import User, UserRole, Organization
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, Token, LoginRequest,
    OrganizationCreate, OrganizationResponse,
)
from app.services.audit_service import AuditService
from app.models.base import generate_uuid

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(data={"sub": user.id})
    await AuditService.log(db, "login", "user", user.id, user.id)
    return Token(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=UserResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=generate_uuid(),
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=UserRole(data.role) if data.role in [r.value for r in UserRole] else UserRole.ANALYST,
        organization_id=data.organization_id,
        preferred_language=data.preferred_language,
    )
    db.add(user)
    await db.flush()
    await AuditService.log(db, "register", "user", user.id, user.id)
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(data: UserUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.preferred_language is not None:
        current_user.preferred_language = data.preferred_language
    await db.flush()
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(status_code=403, detail="Not authorized")
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/organizations", response_model=OrganizationResponse)
async def create_organization(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    org = Organization(
        id=generate_uuid(),
        name=data.name,
        name_ar=data.name_ar,
        license_number=data.license_number,
        org_type=data.org_type,
        country=data.country,
    )
    db.add(org)
    await db.flush()
    await AuditService.log(db, "create_organization", "organization", org.id, current_user.id)
    return OrganizationResponse.model_validate(org)


@router.get("/organizations", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Organization))
    orgs = result.scalars().all()
    return [OrganizationResponse.model_validate(o) for o in orgs]
