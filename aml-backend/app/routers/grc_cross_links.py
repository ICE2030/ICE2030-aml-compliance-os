"""GRC Cross-Linking API endpoints — Phase G3."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.grc.cross_link_service import CrossLinkService

router = APIRouter(prefix="/api/grc/cross-links", tags=["GRC - Cross-Links"])


@router.get("/{entity_type}/{entity_id}")
async def get_entity_links(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all linked entities for a given entity.

    entity_type: risk | issue | audit_finding | obligation | control | evidence | action
    """
    valid_types = ["risk", "issue", "audit_finding", "obligation", "control", "evidence", "action"]
    if entity_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid entity_type. Must be one of: {valid_types}")
    return await CrossLinkService.get_entity_links(db, entity_type, entity_id)
