"""Insurance Authority (IA) Regulations API endpoints.

Endpoints:
- POST /api/regulatory/insurance-authority/seed     — trigger IA Excel seeding
- GET  /api/regulatory/insurance-authority/stats     — get IA stats from DB
- POST /api/regulatory/insurance-authority/reconcile — run reconciliation (read-only)
- GET  /api/regulatory/insurance-authority/parse-preview — preview parsed data without seeding
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.regulatory.ia_excel_service import IAExcelService

router = APIRouter(
    prefix="/api/regulatory/insurance-authority",
    tags=["Insurance Authority"],
)


@router.post("/seed")
async def seed_ia_regulations(
    force_update: bool = Query(False, description="If true, reconcile and report changes for existing documents"),
    db: AsyncSession = Depends(get_db),
):
    """Seed IA regulations from the bundled Excel file.

    Creates Source → Document → Provision → Obligation chain for all 27 sheets.
    Idempotent: re-running skips existing documents unless force_update=True.
    With force_update=True, changes are reported but never silently overwritten.
    """
    try:
        result = await IAExcelService.seed(db, force_update=force_update)
        await db.commit()
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Seeding failed: {e}")


@router.get("/stats")
async def get_ia_stats(db: AsyncSession = Depends(get_db)):
    """Get current IA regulation statistics from the database."""
    try:
        return await IAExcelService.get_ia_stats(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reconcile")
async def reconcile_ia_regulations(db: AsyncSession = Depends(get_db)):
    """Compare spreadsheet content against existing DB records.

    Read-only operation — does NOT modify any data.
    Reports new, changed, missing, and duplicate provisions.
    """
    try:
        return await IAExcelService.reconcile(db)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/parse-preview")
async def parse_preview(
    sheet: Optional[str] = Query(None, description="Filter to a specific sheet name"),
    limit: int = Query(20, ge=1, le=200, description="Max rows per sheet"),
):
    """Preview parsed and classified data from the Excel file without seeding.

    Useful for inspecting how rows are classified before committing to the DB.
    """
    try:
        parsed = IAExcelService.parse()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    summary = IAExcelService.get_parse_summary(parsed)

    # Add row-level detail for inspection
    preview_sheets = {}
    for sheet_name, rows in parsed.items():
        if sheet and sheet != sheet_name:
            continue
        preview_sheets[sheet_name] = [
            {
                "row_number": r.row_number,
                "hierarchy_level": r.hierarchy_level,
                "section_number": r.section_number,
                "row_class": r.row_class.value,
                "text_en": r.best_text_en[:200] if r.best_text_en else None,
                "text_ar": r.best_text_ar[:200] if r.best_text_ar else None,
                "applied": r.applied,
                "content_hash": r.content_hash,
                "creates_obligation": r.row_class.value in (
                    "obligation", "prohibition", "penalty", "reporting", "guidance"
                ),
            }
            for r in rows[:limit]
        ]

    return {
        "summary": summary,
        "preview": preview_sheets,
    }
