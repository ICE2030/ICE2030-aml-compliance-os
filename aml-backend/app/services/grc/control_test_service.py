"""Control Test service — CRUD and summary."""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.audit import ControlTest, AuditEngagement, TestType, TestResult

logger = logging.getLogger(__name__)


class ControlTestService:
    """Control test CRUD."""

    @staticmethod
    async def create_test(db: AsyncSession, engagement_id: str, data: dict) -> dict:
        result = await db.execute(
            select(AuditEngagement).where(AuditEngagement.id == engagement_id)
        )
        if not result.scalars().first():
            return {"error": "Audit engagement not found"}

        ct = ControlTest(
            id=generate_uuid(),
            engagement_id=engagement_id,
            control_id=data.get("control_id"),
            test_type=TestType(data.get("test_type", "both")),
            procedure=data["procedure"],
            procedure_ar=data.get("procedure_ar"),
            tester=data.get("tester"),
            tester_ar=data.get("tester_ar"),
            test_date=_parse_dt(data.get("test_date")),
            design_result=TestResult(data.get("design_result", "not_tested")),
            operating_result=TestResult(data.get("operating_result", "not_tested")),
            overall_result=TestResult(data.get("overall_result", "not_tested")),
            notes=data.get("notes"),
            notes_ar=data.get("notes_ar"),
            evidence_refs=data.get("evidence_refs"),
            sample_size=data.get("sample_size"),
            exceptions_found=data.get("exceptions_found"),
        )
        db.add(ct)
        await db.flush()
        return _test_to_dict(ct)

    @staticmethod
    async def update_test(db: AsyncSession, test_id: str, data: dict) -> dict:
        result = await db.execute(select(ControlTest).where(ControlTest.id == test_id))
        ct = result.scalars().first()
        if not ct:
            return {"error": "Control test not found"}

        for field in [
            "control_id", "procedure", "procedure_ar",
            "tester", "tester_ar", "notes", "notes_ar",
            "evidence_refs", "sample_size", "exceptions_found",
        ]:
            if field in data:
                setattr(ct, field, data[field])

        if "test_type" in data:
            ct.test_type = TestType(data["test_type"])
        if "design_result" in data:
            ct.design_result = TestResult(data["design_result"])
        if "operating_result" in data:
            ct.operating_result = TestResult(data["operating_result"])
        if "overall_result" in data:
            ct.overall_result = TestResult(data["overall_result"])
        if "test_date" in data:
            ct.test_date = _parse_dt(data["test_date"])

        await db.flush()
        return _test_to_dict(ct)

    @staticmethod
    async def get_test(db: AsyncSession, test_id: str) -> Optional[dict]:
        result = await db.execute(select(ControlTest).where(ControlTest.id == test_id))
        ct = result.scalars().first()
        if not ct:
            return None
        return _test_to_dict(ct)

    @staticmethod
    async def list_tests(
        db: AsyncSession,
        engagement_id: Optional[str] = None,
        control_id: Optional[str] = None,
        result_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        stmt = select(ControlTest)
        if engagement_id:
            stmt = stmt.where(ControlTest.engagement_id == engagement_id)
        if control_id:
            stmt = stmt.where(ControlTest.control_id == control_id)
        if result_filter:
            stmt = stmt.where(ControlTest.overall_result == TestResult(result_filter))

        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(ControlTest.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        tests = result.scalars().all()

        return {
            "items": [_test_to_dict(t) for t in tests],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_test(db: AsyncSession, test_id: str) -> dict:
        result = await db.execute(select(ControlTest).where(ControlTest.id == test_id))
        ct = result.scalars().first()
        if not ct:
            return {"error": "Control test not found"}
        await db.delete(ct)
        await db.flush()
        return {"deleted": test_id}

    @staticmethod
    async def get_test_summary(db: AsyncSession) -> dict:
        total = (await db.execute(
            select(sqla_func.count()).select_from(ControlTest)
        )).scalar() or 0

        result_counts = await db.execute(
            select(ControlTest.overall_result, sqla_func.count())
            .group_by(ControlTest.overall_result)
        )
        by_result = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in result_counts.all()
        }

        return {"total": total, "by_result": by_result}


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _test_to_dict(ct: ControlTest) -> dict:
    return {
        "id": ct.id,
        "engagement_id": ct.engagement_id,
        "control_id": ct.control_id,
        "test_type": ct.test_type.value,
        "procedure": ct.procedure,
        "procedure_ar": ct.procedure_ar,
        "tester": ct.tester,
        "tester_ar": ct.tester_ar,
        "test_date": ct.test_date.isoformat() if ct.test_date else None,
        "design_result": ct.design_result.value,
        "operating_result": ct.operating_result.value,
        "overall_result": ct.overall_result.value,
        "notes": ct.notes,
        "notes_ar": ct.notes_ar,
        "evidence_refs": ct.evidence_refs,
        "sample_size": ct.sample_size,
        "exceptions_found": ct.exceptions_found,
        "created_at": ct.created_at.isoformat() if ct.created_at else None,
        "updated_at": ct.updated_at.isoformat() if ct.updated_at else None,
    }
