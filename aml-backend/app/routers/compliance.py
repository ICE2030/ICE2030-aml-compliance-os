"""Compliance Inquiry Router - answers SAMA/CMA regulatory questions."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_current_user
from app.models.user import User
from app.services.compliance_knowledge_service import ComplianceKnowledgeService

router = APIRouter(prefix="/api/compliance", tags=["Compliance Knowledge Base"])


class ComplianceInquiryRequest(BaseModel):
    question: str
    source: str = "all"  # "sama", "cma", or "all"
    language: str = "en"


class ComplianceSearchRequest(BaseModel):
    query: str
    source: str = "all"
    language: str = "en"
    category: Optional[str] = None


@router.post("/inquiry")
async def compliance_inquiry(
    request: ComplianceInquiryRequest,
    current_user: User = Depends(get_current_user),
):
    """Answer a compliance inquiry using SAMA/CMA knowledge base."""
    result = ComplianceKnowledgeService.answer_inquiry(
        question=request.question,
        source=request.source,
        language=request.language,
    )
    return result


@router.post("/search")
async def search_regulations(
    request: ComplianceSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Search SAMA/CMA regulations by query."""
    results = ComplianceKnowledgeService.search_regulations(
        query=request.query,
        source=request.source,
        language=request.language,
        category=request.category,
    )
    return {"results": results, "count": len(results)}


@router.get("/regulations")
async def get_all_regulations(
    source: str = Query("all", description="Filter by source: sama, cma, or all"),
    language: str = Query("en", description="Language: en or ar"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
):
    """Get all available regulations organized by source."""
    return ComplianceKnowledgeService.get_all_regulations(
        source=source,
        language=language,
        category=category,
    )


@router.get("/categories")
async def get_categories(
    current_user: User = Depends(get_current_user),
):
    """Get all available regulatory categories."""
    return ComplianceKnowledgeService.get_categories()
