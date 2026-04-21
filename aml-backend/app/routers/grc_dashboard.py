"""GRC Dashboard / Executive Command Center API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.grc.grc_dashboard_service import GRCDashboardService

router = APIRouter(prefix="/api/grc/dashboard", tags=["GRC - Dashboard"])


@router.get("")
async def get_executive_summary(db: AsyncSession = Depends(get_db)):
    """Get the GRC executive command center summary.

    Answers:
    1. Where are we exposed?
    2. Why are we exposed?
    3. What should we do now?
    """
    return await GRCDashboardService.get_executive_summary(db)
