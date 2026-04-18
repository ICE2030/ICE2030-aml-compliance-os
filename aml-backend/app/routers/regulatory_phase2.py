"""Phase 2 API endpoints — hybrid retrieval, obligation extraction, review queue, ask/search."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db

router = APIRouter(prefix="/api/regulatory", tags=["Regulatory Intelligence - Phase 2"])


# ── Pydantic Schemas ────────────────────────────────────────────────

class AskRequest(BaseModel):
    query: str
    topic_filter: Optional[str] = None
    regulator_filter: Optional[str] = None
    jurisdiction_filter: Optional[str] = None
    authority_level_filter: Optional[str] = None
    limit: int = 10


class SearchRequest(BaseModel):
    query: str
    topic_filter: Optional[str] = None
    regulator_filter: Optional[str] = None
    jurisdiction_filter: Optional[str] = None
    authority_level_filter: Optional[str] = None
    limit: int = 20


class ExtractRequest(BaseModel):
    provision_id: Optional[str] = None
    document_id: Optional[str] = None


class ReviewRequest(BaseModel):
    decision: str  # approved, rejected, needs_revision
    reviewer_notes: Optional[str] = None
    confidence_adjustment: Optional[float] = None


class BatchReviewRequest(BaseModel):
    obligation_ids: list[str]
    decision: str
    reviewer_notes: Optional[str] = None


class ObligationOut(BaseModel):
    id: str
    text: str
    text_ar: Optional[str] = None
    normalized_summary: Optional[str] = None
    normalized_summary_ar: Optional[str] = None
    obligation_type: str
    applies_to_entity_types: Optional[list] = None
    applies_to_product_types: Optional[list] = None
    condition: Optional[str] = None
    deadline: Optional[str] = None
    confidence: float
    extraction_method: str
    review_status: str
    reviewer_notes: Optional[str] = None
    version: int = 1
    is_active: bool = True
    provision_id: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ── Ask / Search Endpoints ──────────────────────────────────────────

@router.post("/ask")
async def ask_regulatory(req: AskRequest, db: AsyncSession = Depends(get_db)):
    """Ask a regulatory compliance question. Returns an answer with cited sources.

    Every response includes: source title, URL, regulator, jurisdiction,
    authority tier, binding status, confidence, and provision citations.
    """
    from app.services.regulatory.retrieval_service import HybridRetrievalService
    result = await HybridRetrievalService.ask(
        db, req.query, req.topic_filter, req.regulator_filter,
        req.jurisdiction_filter, req.authority_level_filter, req.limit,
    )
    await db.commit()  # persist QueryLog
    return result


@router.post("/search")
async def search_regulatory(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Search across the regulatory knowledge base using hybrid retrieval.

    Returns matching provisions with full provenance (source, regulator,
    jurisdiction, authority level, binding status) and relevance scores.
    """
    from app.services.regulatory.retrieval_service import HybridRetrievalService
    result = await HybridRetrievalService.search(
        db, req.query, req.topic_filter, req.regulator_filter,
        req.jurisdiction_filter, req.authority_level_filter, req.limit,
    )

    # Convert citations to dicts
    citations = []
    for c in result.citations:
        citations.append({
            "source_title": c.source_title,
            "source_title_ar": c.source_title_ar,
            "source_url": c.source_url,
            "regulator": c.regulator_name,
            "regulator_abbreviation": c.regulator_abbreviation,
            "jurisdiction": c.jurisdiction_name,
            "jurisdiction_code": c.jurisdiction_code,
            "authority_level": c.authority_level,
            "is_binding": c.is_binding,
            "binding_status": "Binding" if c.is_binding else "Non-binding",
            "provision_id": c.provision_id,
            "provision_section": c.provision_section,
            "provision_title": c.provision_title,
            "provision_text": c.provision_text,
            "provision_text_ar": c.provision_text_ar,
            "relevance_score": c.relevance_score,
            "retrieval_method": c.retrieval_method,
        })

    return {
        "query": result.query,
        "total_results": result.total_results,
        "confidence": result.confidence,
        "topics_matched": result.topics_matched,
        "retrieval_methods_used": result.retrieval_methods_used,
        "results": citations,
        "gaps_detected": result.gaps_detected,
    }


# ── Obligation Extraction Endpoints ─────────────────────────────────

@router.post("/obligations/extract")
async def extract_obligations(req: ExtractRequest, db: AsyncSession = Depends(get_db)):
    """Extract obligations from a provision or document using rule-based + AI-assisted analysis.

    Returns structured JSON for each extracted obligation.
    """
    from app.services.regulatory.obligation_extraction_service import ObligationExtractionService

    if not req.provision_id and not req.document_id:
        raise HTTPException(status_code=400, detail="Either provision_id or document_id is required")

    if req.provision_id:
        obligations = await ObligationExtractionService.extract_from_provision(db, req.provision_id)
    else:
        obligations = await ObligationExtractionService.extract_from_document(db, req.document_id)

    await db.commit()

    return {
        "extracted": len(obligations),
        "obligations": [
            {
                "id": ob.id,
                "text": ob.text,
                "text_ar": ob.text_ar,
                "normalized_summary": ob.normalized_summary,
                "obligation_type": ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type),
                "applies_to_entity_types": ob.applies_to_entity_types,
                "condition": ob.condition,
                "deadline": ob.deadline,
                "confidence": ob.confidence,
                "extraction_method": ob.extraction_method.value if hasattr(ob.extraction_method, 'value') else str(ob.extraction_method),
                "review_status": ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status),
                "provision_id": ob.provision_id,
            }
            for ob in obligations
        ],
    }


class ExtractAllRequest(BaseModel):
    force: bool = False  # If True, delete all existing obligations before re-extracting


@router.post("/obligations/extract-all")
async def extract_all_obligations(
    req: Optional[ExtractAllRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Extract obligations from ALL provisions in the database.

    By default, only processes provisions without existing obligations.
    Pass {"force": true} to delete all existing obligations and re-extract
    from scratch (useful after hardening changes to extraction logic).
    """
    from sqlalchemy import select, delete as sql_delete
    from app.models.regulatory.source import Provision
    from app.models.regulatory.obligation import Obligation
    from app.models.regulatory.change import ReviewDecision
    from app.services.regulatory.obligation_extraction_service import ObligationExtractionService

    deleted_count = 0
    if req and req.force:
        # Delete review decisions first (FK constraint), then obligations
        await db.execute(sql_delete(ReviewDecision))
        result = await db.execute(sql_delete(Obligation))
        deleted_count = result.rowcount
        await db.flush()

    # Get all provision IDs
    prov_result = await db.execute(select(Provision.id))
    all_prov_ids = [row[0] for row in prov_result.all()]

    # Get provision IDs that already have obligations
    existing_result = await db.execute(
        select(Obligation.provision_id).distinct()
    )
    existing_prov_ids = {row[0] for row in existing_result.all()}

    # Only process provisions without obligations
    new_prov_ids = [pid for pid in all_prov_ids if pid not in existing_prov_ids]

    total_extracted = 0
    for prov_id in new_prov_ids:
        obligations = await ObligationExtractionService.extract_from_provision(db, prov_id)
        total_extracted += len(obligations)

    await db.commit()

    return {
        "total_provisions": len(all_prov_ids),
        "provisions_processed": len(new_prov_ids),
        "provisions_skipped": len(existing_prov_ids),
        "obligations_extracted": total_extracted,
        "deleted_pre_existing": deleted_count,
    }


@router.get("/obligations")
async def list_obligations(
    review_status: Optional[str] = None,
    obligation_type: Optional[str] = None,
    extraction_method: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    regulator_filter: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List obligations with filters. Supports the review queue workflow."""
    from app.services.regulatory.review_service import ReviewQueueService
    items, total = await ReviewQueueService.get_queue(
        db, review_status, obligation_type, regulator_filter,
        min_confidence, max_confidence, extraction_method, skip, limit,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/obligations/stats")
async def get_obligation_stats(db: AsyncSession = Depends(get_db)):
    """Get obligation extraction and review statistics."""
    from app.services.regulatory.review_service import ReviewQueueService
    return await ReviewQueueService.get_review_stats(db)


@router.get("/obligations/{obligation_id}")
async def get_obligation(obligation_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single obligation by ID with full provenance."""
    from app.services.regulatory.review_service import ReviewQueueService
    items, _ = await ReviewQueueService.get_queue(db, limit=1)
    # Fetch directly
    from app.models.regulatory.obligation import Obligation
    ob = await db.get(Obligation, obligation_id)
    if not ob:
        raise HTTPException(status_code=404, detail="Obligation not found")

    result = {
        "id": ob.id,
        "text": ob.text,
        "text_ar": ob.text_ar,
        "normalized_summary": ob.normalized_summary,
        "normalized_summary_ar": ob.normalized_summary_ar,
        "obligation_type": ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type),
        "applies_to_entity_types": ob.applies_to_entity_types,
        "applies_to_product_types": ob.applies_to_product_types,
        "condition": ob.condition,
        "deadline": ob.deadline,
        "confidence": ob.confidence,
        "extraction_method": ob.extraction_method.value if hasattr(ob.extraction_method, 'value') else str(ob.extraction_method),
        "review_status": ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status),
        "reviewer_notes": ob.reviewer_notes,
        "version": ob.version,
        "is_active": ob.is_active,
        "provision_id": ob.provision_id,
    }

    # Enrich with provision context
    from app.models.regulatory.source import Provision, RegulatoryDocument, Regulator, Jurisdiction
    provision = await db.get(Provision, ob.provision_id)
    if provision:
        result["provision_section"] = provision.section_number
        result["provision_title"] = provision.title
        result["provision_text"] = provision.text
        result["provision_text_ar"] = provision.text_ar

        doc = await db.get(RegulatoryDocument, provision.document_id)
        if doc:
            regulator = await db.get(Regulator, doc.regulator_id)
            jurisdiction = await db.get(Jurisdiction, doc.jurisdiction_id)
            result["regulator_name"] = regulator.name if regulator else None
            result["regulator_abbreviation"] = regulator.abbreviation if regulator else None
            result["jurisdiction_name"] = jurisdiction.name if jurisdiction else None

    return result


# ── Review Queue Endpoints ──────────────────────────────────────────

@router.post("/obligations/{obligation_id}/review")
async def review_obligation(
    obligation_id: str,
    req: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a review decision for an obligation.

    Valid decisions: approved, rejected, needs_revision.
    Creates an audit trail via ReviewDecision records.
    """
    from app.services.regulatory.review_service import ReviewQueueService

    if req.decision not in ("approved", "rejected", "needs_revision"):
        raise HTTPException(
            status_code=400,
            detail="Decision must be one of: approved, rejected, needs_revision",
        )

    result = await ReviewQueueService.review_obligation(
        db, obligation_id, req.decision, req.reviewer_notes, req.confidence_adjustment,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Obligation not found")

    await db.commit()
    return result


@router.post("/obligations/batch-review")
async def batch_review_obligations(
    req: BatchReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Batch review multiple obligations at once."""
    from app.services.regulatory.review_service import ReviewQueueService

    if req.decision not in ("approved", "rejected", "needs_revision"):
        raise HTTPException(
            status_code=400,
            detail="Decision must be one of: approved, rejected, needs_revision",
        )

    result = await ReviewQueueService.batch_review(
        db, req.obligation_ids, req.decision, req.reviewer_notes,
    )
    await db.commit()
    return result


@router.get("/review-stats")
async def get_review_stats(db: AsyncSession = Depends(get_db)):
    """Get review queue statistics — total obligations, by status, by type, avg confidence."""
    from app.services.regulatory.review_service import ReviewQueueService
    return await ReviewQueueService.get_review_stats(db)
