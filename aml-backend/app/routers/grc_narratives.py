"""GRC Narrative Layer API endpoints — Phase G3."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.narrative_service import NarrativeService

router = APIRouter(prefix="/api/grc/narratives", tags=["GRC - Narrative Layer"])


@router.post("/generate")
async def generate_executive_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Generate an AI-powered executive narrative summary. Clearly marked as AI-generated."""
    result = await NarrativeService.generate_executive_summary(db)
    await db.commit()
    return result


@router.get("")
async def list_narratives(
    narrative_type: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List narrative summaries."""
    return await NarrativeService.list_narratives(db, narrative_type=narrative_type, limit=limit, offset=offset)


@router.get("/{narrative_id}")
async def get_narrative(narrative_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single narrative."""
    result = await NarrativeService.get_narrative(db, narrative_id)
    if not result:
        raise HTTPException(status_code=404, detail="Narrative not found")
    return result


@router.put("/{narrative_id}")
async def update_narrative(narrative_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Edit a narrative (user override of AI-generated content)."""
    result = await NarrativeService.update_narrative(db, narrative_id, data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result


@router.delete("/{narrative_id}")
async def delete_narrative(narrative_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a narrative."""
    result = await NarrativeService.delete_narrative(db, narrative_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    await db.commit()
    return result
