"""Control Test API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.control_test_service import ControlTestService

router = APIRouter(prefix="/api/grc/control-tests", tags=["GRC - Control Tests"])


@router.post("/{engagement_id}")
async def create_test(engagement_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a control test within an engagement."""
    result = await ControlTestService.create_test(db, engagement_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.get("")
async def list_tests(
    engagement_id: str = Query(None),
    control_id: str = Query(None),
    result_filter: str = Query(None, alias="result"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List control tests with optional filters."""
    return await ControlTestService.list_tests(
        db, engagement_id=engagement_id, control_id=control_id,
        result_filter=result_filter, limit=limit, offset=offset,
    )


@router.get("/summary")
async def get_test_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get control test summary stats."""
    return await ControlTestService.get_test_summary(db)


@router.get("/{test_id}")
async def get_test(test_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single control test."""
    result = await ControlTestService.get_test(db, test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Control test not found")
    return result


@router.put("/{test_id}")
async def update_test(test_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update a control test."""
    result = await ControlTestService.update_test(db, test_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.delete("/{test_id}")
async def delete_test(test_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a control test."""
    result = await ControlTestService.delete_test(db, test_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result
