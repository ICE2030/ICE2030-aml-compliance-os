"""Enterprise Risk Register API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.enterprise_risk_service import EnterpriseRiskService, RiskCategoryService

router = APIRouter(prefix="/api/grc/risks", tags=["GRC - Enterprise Risk"])


@router.post("")
async def create_risk(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new enterprise risk."""
    result = await EnterpriseRiskService.create_risk(db, data)
    await db.commit()
    return result


@router.get("")
async def list_risks(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity_min: Optional[float] = Query(None),
    business_unit: Optional[str] = Query(None),
    regulator_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List enterprise risks with filtering."""
    return await EnterpriseRiskService.list_risks(
        db, category=category, status=status,
        severity_min=severity_min, business_unit=business_unit,
        regulator_id=regulator_id, limit=limit, offset=offset,
    )


@router.get("/summary")
async def get_risk_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get risk register summary statistics."""
    return await EnterpriseRiskService.get_risk_summary(db)


@router.get("/heatmap")
async def get_risk_heatmap(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get risk heatmap data (likelihood x impact)."""
    return await EnterpriseRiskService.get_risk_heatmap(db)


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all risk categories."""
    return await RiskCategoryService.list_categories(db)


@router.post("/categories/seed")
async def seed_categories(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Seed default risk categories."""
    result = await RiskCategoryService.seed_default_categories(db)
    await db.commit()
    return result


@router.get("/{risk_id}")
async def get_risk(risk_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single enterprise risk."""
    result = await EnterpriseRiskService.get_risk(db, risk_id)
    if not result:
        raise HTTPException(status_code=404, detail="Risk not found")
    return result


@router.put("/{risk_id}")
async def update_risk(risk_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update an enterprise risk."""
    result = await EnterpriseRiskService.update_risk(db, risk_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.delete("/{risk_id}")
async def delete_risk(risk_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete an enterprise risk."""
    result = await EnterpriseRiskService.delete_risk(db, risk_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.post("/{risk_id}/snapshot")
async def capture_snapshot(risk_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Capture a point-in-time snapshot of a risk."""
    result = await EnterpriseRiskService.capture_snapshot(db, risk_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result
