"""Regulatory Intelligence API endpoints - Phase 1: Source registry, regulators, packs."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.services.regulatory.source_registry_service import SourceRegistryService

router = APIRouter(prefix="/api/regulatory", tags=["Regulatory Intelligence"])


# --- Pydantic schemas ---

class JurisdictionOut(BaseModel):
    id: str
    name: str
    name_ar: Optional[str] = None
    code: str
    region: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class RegulatorOut(BaseModel):
    id: str
    name: str
    name_ar: Optional[str] = None
    abbreviation: str
    jurisdiction_id: str
    website: Optional[str] = None
    source_url: Optional[str] = None
    regulator_type: str = "financial"
    description: Optional[str] = None
    description_ar: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class SourceOut(BaseModel):
    id: str
    regulator_id: str
    title: str
    title_ar: Optional[str] = None
    url: Optional[str] = None
    source_type: str
    authority_level: str
    jurisdiction_id: str
    language: str = "en"
    is_monitored: bool = True
    crawl_frequency: str = "weekly"
    last_crawled: Optional[str] = None
    last_crawl_status: Optional[str] = None
    status: str = "active"
    pack_id: Optional[str] = None
    seed_key: Optional[str] = None

    class Config:
        from_attributes = True


class SourceCreateIn(BaseModel):
    regulator_id: str
    title: str
    title_ar: Optional[str] = None
    url: Optional[str] = None
    source_type: str = "regulation"
    authority_level: str = "tier_1"
    jurisdiction_id: str
    language: str = "en"
    crawl_frequency: str = "weekly"


class SourceUpdateIn(BaseModel):
    title: Optional[str] = None
    title_ar: Optional[str] = None
    url: Optional[str] = None
    source_type: Optional[str] = None
    authority_level: Optional[str] = None
    language: Optional[str] = None
    crawl_frequency: Optional[str] = None
    is_monitored: Optional[bool] = None
    status: Optional[str] = None


class TopicOut(BaseModel):
    id: str
    name: str
    name_ar: Optional[str] = None
    category: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class DashboardStatsOut(BaseModel):
    total_sources: int = 0
    monitored_sources: int = 0
    total_regulators: int = 0
    total_jurisdictions: int = 0
    total_documents: int = 0
    total_provisions: int = 0
    total_topics: int = 0
    sources_by_status: dict = {}
    sources_by_authority: dict = {}


class PackInfoOut(BaseModel):
    pack_id: str
    regulator: str
    regulator_ar: str
    abbreviation: str
    jurisdiction: str
    jurisdiction_code: str
    sources_count: int
    topics_count: int
    provisions_count: int
    issues: list[str] = []


class SeedResultOut(BaseModel):
    packs_loaded: int = 0
    jurisdictions: int = 0
    regulators: int = 0
    sources: int = 0
    topics: int = 0
    provisions: int = 0
    source_topics: int = 0
    sources_updated: int = 0


class SourceVersionOut(BaseModel):
    id: str
    source_id: str
    version_number: int
    fetched_at: Optional[str] = None
    content_hash: str
    is_current: bool = True
    parser_confidence: Optional[float] = None

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.get("/dashboard", response_model=DashboardStatsOut)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get regulatory intelligence dashboard statistics."""
    stats = await SourceRegistryService.get_dashboard_stats(db)
    return stats


@router.get("/jurisdictions", response_model=list[JurisdictionOut])
async def list_jurisdictions(db: AsyncSession = Depends(get_db)):
    """List all jurisdictions."""
    return await SourceRegistryService.get_jurisdictions(db)


@router.get("/regulators", response_model=list[RegulatorOut])
async def list_regulators(
    jurisdiction_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List regulators, optionally filtered by jurisdiction."""
    return await SourceRegistryService.get_regulators(db, jurisdiction_id)


@router.get("/sources", response_model=dict)
async def list_sources(
    regulator_id: Optional[str] = None,
    source_type: Optional[str] = None,
    authority_level: Optional[str] = None,
    status: Optional[str] = None,
    is_monitored: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List regulatory sources with filters."""
    sources, total = await SourceRegistryService.get_sources(
        db, regulator_id, source_type, authority_level, status, is_monitored, skip, limit,
    )
    return {
        "items": [SourceOut.model_validate(s) for s in sources],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/sources/{source_id}", response_model=SourceOut)
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single source by ID."""
    source = await SourceRegistryService.get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/sources", response_model=SourceOut, status_code=201)
async def create_source(data: SourceCreateIn, db: AsyncSession = Depends(get_db)):
    """Register a new regulatory source."""
    source = await SourceRegistryService.create_source(db, **data.model_dump())
    await db.commit()
    return source


@router.put("/sources/{source_id}", response_model=SourceOut)
async def update_source(source_id: str, data: SourceUpdateIn, db: AsyncSession = Depends(get_db)):
    """Update an existing regulatory source."""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    source = await SourceRegistryService.update_source(db, source_id, **update_data)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.commit()
    return source


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a regulatory source."""
    deleted = await SourceRegistryService.delete_source(db, source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.commit()
    return None


@router.get("/sources/{source_id}/versions", response_model=list[SourceVersionOut])
async def list_source_versions(source_id: str, db: AsyncSession = Depends(get_db)):
    """List all versions of a source."""
    return await SourceRegistryService.get_source_versions(db, source_id)


@router.get("/topics", response_model=list[TopicOut])
async def list_topics(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List regulatory topics."""
    return await SourceRegistryService.get_topics(db, category)


@router.get("/packs", response_model=list[PackInfoOut])
async def list_packs():
    """List available regulator packs."""
    from regulator_packs.pack_loader import list_packs
    return list_packs()


@router.post("/seed", response_model=SeedResultOut)
async def seed_all_packs(db: AsyncSession = Depends(get_db)):
    """Seed database with all regulator pack data (idempotent)."""
    from app.services.regulatory.seed_service import SeedService
    result = await SeedService.seed_all_packs(db)
    await db.commit()
    return result


@router.post("/seed/{pack_id}", response_model=dict)
async def seed_single_pack(pack_id: str, db: AsyncSession = Depends(get_db)):
    """Seed database with a single regulator pack."""
    from regulator_packs.pack_loader import load_pack
    from app.services.regulatory.seed_service import SeedService
    pack = load_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_id}")
    result = await SeedService.seed_pack(db, pack)
    await db.commit()
    return result
