"""Enterprise Risk Management service.

Handles:
- Risk CRUD with inherent/residual scoring
- Risk snapshots for trend tracking
- Risk heatmap data
- Links to obligations, controls, regulators
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func as sqla_func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import generate_uuid
from app.models.grc.enterprise_risk import (
    EnterpriseRisk, RiskCategory, RiskSnapshot,
    RiskCategoryEnum, LikelihoodLevel, ImpactLevel,
    TreatmentStrategy, RiskStatus, TrendDirection,
)

logger = logging.getLogger(__name__)

# Scoring matrices
_LIKELIHOOD_SCORES = {
    LikelihoodLevel.RARE: 1,
    LikelihoodLevel.UNLIKELY: 2,
    LikelihoodLevel.POSSIBLE: 3,
    LikelihoodLevel.LIKELY: 4,
    LikelihoodLevel.ALMOST_CERTAIN: 5,
}

_IMPACT_SCORES = {
    ImpactLevel.INSIGNIFICANT: 1,
    ImpactLevel.MINOR: 2,
    ImpactLevel.MODERATE: 3,
    ImpactLevel.MAJOR: 4,
    ImpactLevel.SEVERE: 5,
}


def compute_risk_score(likelihood: LikelihoodLevel, impact: ImpactLevel) -> float:
    """Compute risk score as likelihood * impact, normalized to 0-1 scale (max=25)."""
    raw = _LIKELIHOOD_SCORES[likelihood] * _IMPACT_SCORES[impact]
    return round(raw / 25.0, 4)


class EnterpriseRiskService:
    """Enterprise risk register CRUD and scoring."""

    @staticmethod
    async def create_risk(db: AsyncSession, data: dict) -> dict:
        """Create a new enterprise risk with auto-computed scores."""
        inherent_likelihood = LikelihoodLevel(data.get("inherent_likelihood", "possible"))
        inherent_impact = ImpactLevel(data.get("inherent_impact", "moderate"))
        residual_likelihood = LikelihoodLevel(data.get("residual_likelihood", inherent_likelihood.value))
        residual_impact = ImpactLevel(data.get("residual_impact", inherent_impact.value))

        risk = EnterpriseRisk(
            id=generate_uuid(),
            title=data["title"],
            title_ar=data.get("title_ar"),
            description=data["description"],
            description_ar=data.get("description_ar"),
            category=RiskCategoryEnum(data.get("category", "operational")),
            subcategory=data.get("subcategory"),
            category_id=data.get("category_id"),
            business_unit=data.get("business_unit"),
            business_unit_ar=data.get("business_unit_ar"),
            process=data.get("process"),
            process_ar=data.get("process_ar"),
            regulator_id=data.get("regulator_id"),
            obligation_id=data.get("obligation_id"),
            topic_id=data.get("topic_id"),
            root_cause=data.get("root_cause"),
            root_cause_ar=data.get("root_cause_ar"),
            inherent_likelihood=inherent_likelihood,
            inherent_impact=inherent_impact,
            inherent_score=compute_risk_score(inherent_likelihood, inherent_impact),
            residual_likelihood=residual_likelihood,
            residual_impact=residual_impact,
            residual_score=compute_risk_score(residual_likelihood, residual_impact),
            treatment_strategy=TreatmentStrategy(data.get("treatment_strategy", "mitigate")),
            treatment_plan=data.get("treatment_plan"),
            treatment_plan_ar=data.get("treatment_plan_ar"),
            control_environment=data.get("control_environment"),
            control_environment_ar=data.get("control_environment_ar"),
            owner=data.get("owner"),
            owner_ar=data.get("owner_ar"),
            status=RiskStatus(data.get("status", "identified")),
            trend_direction=TrendDirection(data.get("trend_direction", "new")),
            risk_factors=data.get("risk_factors"),
        )
        db.add(risk)
        await db.flush()
        return _risk_to_dict(risk)

    @staticmethod
    async def update_risk(db: AsyncSession, risk_id: str, data: dict) -> dict:
        """Update an enterprise risk and recompute scores."""
        result = await db.execute(
            select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id)
        )
        risk = result.scalars().first()
        if not risk:
            return {"error": "Risk not found"}

        for field in [
            "title", "title_ar", "description", "description_ar",
            "subcategory", "business_unit", "business_unit_ar",
            "process", "process_ar", "root_cause", "root_cause_ar",
            "treatment_plan", "treatment_plan_ar",
            "control_environment", "control_environment_ar",
            "owner", "owner_ar", "risk_factors",
            "regulator_id", "obligation_id", "topic_id", "category_id",
        ]:
            if field in data:
                setattr(risk, field, data[field])

        if "category" in data:
            risk.category = RiskCategoryEnum(data["category"])
        if "status" in data:
            risk.status = RiskStatus(data["status"])
        if "trend_direction" in data:
            risk.trend_direction = TrendDirection(data["trend_direction"])
        if "treatment_strategy" in data:
            risk.treatment_strategy = TreatmentStrategy(data["treatment_strategy"])

        # Recompute scores if likelihood/impact changed
        if "inherent_likelihood" in data:
            risk.inherent_likelihood = LikelihoodLevel(data["inherent_likelihood"])
        if "inherent_impact" in data:
            risk.inherent_impact = ImpactLevel(data["inherent_impact"])
        risk.inherent_score = compute_risk_score(risk.inherent_likelihood, risk.inherent_impact)

        if "residual_likelihood" in data:
            risk.residual_likelihood = LikelihoodLevel(data["residual_likelihood"])
        if "residual_impact" in data:
            risk.residual_impact = ImpactLevel(data["residual_impact"])
        risk.residual_score = compute_risk_score(risk.residual_likelihood, risk.residual_impact)

        if "review_date" in data and data["review_date"]:
            risk.review_date = datetime.fromisoformat(data["review_date"])

        await db.flush()
        return _risk_to_dict(risk)

    @staticmethod
    async def get_risk(db: AsyncSession, risk_id: str) -> Optional[dict]:
        """Get a single risk by ID."""
        result = await db.execute(
            select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id)
        )
        risk = result.scalars().first()
        if not risk:
            return None
        return _risk_to_dict(risk)

    @staticmethod
    async def list_risks(
        db: AsyncSession,
        category: Optional[str] = None,
        status: Optional[str] = None,
        severity_min: Optional[float] = None,
        business_unit: Optional[str] = None,
        regulator_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List risks with filtering."""
        stmt = select(EnterpriseRisk)

        if category:
            stmt = stmt.where(EnterpriseRisk.category == RiskCategoryEnum(category))
        if status:
            stmt = stmt.where(EnterpriseRisk.status == RiskStatus(status))
        if severity_min is not None:
            stmt = stmt.where(EnterpriseRisk.residual_score >= severity_min)
        if business_unit:
            stmt = stmt.where(EnterpriseRisk.business_unit == business_unit)
        if regulator_id:
            stmt = stmt.where(EnterpriseRisk.regulator_id == regulator_id)

        # Count
        count_stmt = select(sqla_func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(EnterpriseRisk.residual_score.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        risks = result.scalars().all()

        return {
            "items": [_risk_to_dict(r) for r in risks],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def delete_risk(db: AsyncSession, risk_id: str) -> dict:
        """Delete a risk."""
        result = await db.execute(
            select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id)
        )
        risk = result.scalars().first()
        if not risk:
            return {"error": "Risk not found"}
        await db.delete(risk)
        await db.flush()
        return {"deleted": risk_id}

    @staticmethod
    async def capture_snapshot(db: AsyncSession, risk_id: str) -> dict:
        """Capture a point-in-time snapshot of a risk."""
        result = await db.execute(
            select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id)
        )
        risk = result.scalars().first()
        if not risk:
            return {"error": "Risk not found"}

        snapshot = RiskSnapshot(
            id=generate_uuid(),
            risk_id=risk_id,
            snapshot_at=datetime.now(timezone.utc),
            inherent_score=risk.inherent_score,
            residual_score=risk.residual_score,
            status=risk.status.value,
            trend_direction=risk.trend_direction.value,
        )
        db.add(snapshot)
        await db.flush()
        return {
            "id": snapshot.id,
            "risk_id": risk_id,
            "snapshot_at": snapshot.snapshot_at.isoformat(),
            "inherent_score": snapshot.inherent_score,
            "residual_score": snapshot.residual_score,
        }

    @staticmethod
    async def get_risk_heatmap(db: AsyncSession) -> dict:
        """Get heatmap data: count of risks by likelihood x impact (residual)."""
        result = await db.execute(select(EnterpriseRisk))
        risks = result.scalars().all()

        heatmap = {}
        for r in risks:
            key = f"{r.residual_likelihood.value}|{r.residual_impact.value}"
            if key not in heatmap:
                heatmap[key] = {"likelihood": r.residual_likelihood.value, "impact": r.residual_impact.value, "count": 0, "risks": []}
            heatmap[key]["count"] += 1
            heatmap[key]["risks"].append({"id": r.id, "title": r.title, "score": r.residual_score})

        return {
            "cells": list(heatmap.values()),
            "total_risks": len(risks),
        }

    @staticmethod
    async def get_risk_summary(db: AsyncSession) -> dict:
        """Get summary stats for the risk register."""
        total = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk)
        )).scalar() or 0

        high_risks = (await db.execute(
            select(sqla_func.count()).select_from(EnterpriseRisk).where(
                EnterpriseRisk.residual_score >= 0.48  # 12/25 = major+likely
            )
        )).scalar() or 0

        # By category
        cat_result = await db.execute(
            select(EnterpriseRisk.category, sqla_func.count())
            .group_by(EnterpriseRisk.category)
        )
        by_category = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in cat_result.all()
        }

        # By status
        status_result = await db.execute(
            select(EnterpriseRisk.status, sqla_func.count())
            .group_by(EnterpriseRisk.status)
        )
        by_status = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in status_result.all()
        }

        # By trend
        trend_result = await db.execute(
            select(EnterpriseRisk.trend_direction, sqla_func.count())
            .group_by(EnterpriseRisk.trend_direction)
        )
        by_trend = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in trend_result.all()
        }

        # Avg scores
        avg_inherent = (await db.execute(
            select(sqla_func.avg(EnterpriseRisk.inherent_score))
        )).scalar() or 0
        avg_residual = (await db.execute(
            select(sqla_func.avg(EnterpriseRisk.residual_score))
        )).scalar() or 0

        return {
            "total": total,
            "high_risks": high_risks,
            "by_category": by_category,
            "by_status": by_status,
            "by_trend": by_trend,
            "avg_inherent_score": round(float(avg_inherent), 4),
            "avg_residual_score": round(float(avg_residual), 4),
        }


class RiskCategoryService:
    """Risk category taxonomy management."""

    @staticmethod
    async def seed_default_categories(db: AsyncSession) -> dict:
        """Seed default risk categories if none exist."""
        existing = (await db.execute(
            select(sqla_func.count()).select_from(RiskCategory)
        )).scalar() or 0
        if existing > 0:
            return {"seeded": 0, "existing": existing}

        categories = [
            ("Regulatory Risk", "المخاطر التنظيمية", RiskCategoryEnum.REGULATORY, "Non-compliance with laws and regulations"),
            ("Compliance Risk", "مخاطر الامتثال", RiskCategoryEnum.COMPLIANCE, "Failure to meet compliance obligations"),
            ("Operational Risk", "المخاطر التشغيلية", RiskCategoryEnum.OPERATIONAL, "Losses from processes, people, or systems"),
            ("Fraud Risk", "مخاطر الاحتيال", RiskCategoryEnum.FRAUD, "Internal or external fraud exposure"),
            ("Strategic Risk", "المخاطر الاستراتيجية", RiskCategoryEnum.STRATEGIC, "Risks to business strategy and objectives"),
            ("Financial Risk", "المخاطر المالية", RiskCategoryEnum.FINANCIAL, "Financial loss exposure"),
            ("Technology Risk", "مخاطر التكنولوجيا", RiskCategoryEnum.TECHNOLOGY, "IT, cyber, and data risks"),
            ("Third-Party Risk", "مخاطر الطرف الثالث", RiskCategoryEnum.THIRD_PARTY, "Risks from vendors and partners"),
            ("Conduct Risk", "مخاطر السلوك", RiskCategoryEnum.CONDUCT, "Misconduct and ethical violations"),
            ("Reputational Risk", "مخاطر السمعة", RiskCategoryEnum.REPUTATIONAL, "Damage to organizational reputation"),
        ]

        created = 0
        for name, name_ar, cat, desc in categories:
            rc = RiskCategory(
                id=generate_uuid(),
                name=name,
                name_ar=name_ar,
                category=cat,
                description=desc,
            )
            db.add(rc)
            created += 1

        await db.flush()
        return {"seeded": created}

    @staticmethod
    async def list_categories(db: AsyncSession) -> list:
        """List all risk categories."""
        result = await db.execute(
            select(RiskCategory).order_by(RiskCategory.name)
        )
        return [
            {
                "id": c.id,
                "name": c.name,
                "name_ar": c.name_ar,
                "category": c.category.value,
                "subcategory": c.subcategory,
                "description": c.description,
            }
            for c in result.scalars().all()
        ]


def _risk_to_dict(risk: EnterpriseRisk) -> dict:
    """Serialize an EnterpriseRisk to dict."""
    return {
        "id": risk.id,
        "title": risk.title,
        "title_ar": risk.title_ar,
        "description": risk.description,
        "description_ar": risk.description_ar,
        "category": risk.category.value,
        "subcategory": risk.subcategory,
        "category_id": risk.category_id,
        "business_unit": risk.business_unit,
        "business_unit_ar": risk.business_unit_ar,
        "process": risk.process,
        "regulator_id": risk.regulator_id,
        "obligation_id": risk.obligation_id,
        "topic_id": risk.topic_id,
        "root_cause": risk.root_cause,
        "inherent_likelihood": risk.inherent_likelihood.value,
        "inherent_impact": risk.inherent_impact.value,
        "inherent_score": risk.inherent_score,
        "control_environment": risk.control_environment,
        "residual_likelihood": risk.residual_likelihood.value,
        "residual_impact": risk.residual_impact.value,
        "residual_score": risk.residual_score,
        "treatment_strategy": risk.treatment_strategy.value,
        "treatment_plan": risk.treatment_plan,
        "owner": risk.owner,
        "owner_ar": risk.owner_ar,
        "status": risk.status.value,
        "trend_direction": risk.trend_direction.value,
        "review_date": risk.review_date.isoformat() if risk.review_date else None,
        "risk_factors": risk.risk_factors,
        "created_at": risk.created_at.isoformat() if risk.created_at else None,
        "updated_at": risk.updated_at.isoformat() if risk.updated_at else None,
    }
