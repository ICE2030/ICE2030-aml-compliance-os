import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entity import Entity, RiskLevel
from app.models.risk import RiskRule, RiskAssessment
from app.models.base import generate_uuid

# High-risk countries list (FATF grey/black list examples)
HIGH_RISK_COUNTRIES = ["IR", "KP", "MM", "SY", "YE", "AF"]
MEDIUM_RISK_COUNTRIES = ["PK", "LB", "IQ", "LY", "SO"]

# High-risk industries
HIGH_RISK_INDUSTRIES = ["money_exchange", "cryptocurrency", "gambling", "arms_trade", "precious_metals"]
MEDIUM_RISK_INDUSTRIES = ["real_estate", "construction", "import_export", "cash_intensive"]


class RiskScoringService:
    @staticmethod
    async def assess_entity(
        db: AsyncSession,
        entity_id: str,
        user_id: Optional[str] = None,
    ) -> RiskAssessment:
        result = await db.execute(select(Entity).where(Entity.id == entity_id))
        entity = result.scalar_one_or_none()
        if not entity:
            raise ValueError("Entity not found")

        total_score = 0.0
        matched_rules = []

        # 1. Country risk
        country = entity.country or "SA"
        if country in HIGH_RISK_COUNTRIES:
            total_score += 30
            matched_rules.append({"rule": "High-risk country", "field": "country", "value": country, "impact": 30})
        elif country in MEDIUM_RISK_COUNTRIES:
            total_score += 15
            matched_rules.append({"rule": "Medium-risk country", "field": "country", "value": country, "impact": 15})

        # 2. Nationality risk (for individuals)
        if entity.nationality and entity.nationality in HIGH_RISK_COUNTRIES:
            total_score += 25
            matched_rules.append({"rule": "High-risk nationality", "field": "nationality", "value": entity.nationality, "impact": 25})

        # 3. Industry risk (for companies)
        if entity.industry:
            industry_lower = entity.industry.lower().replace(" ", "_")
            if industry_lower in HIGH_RISK_INDUSTRIES:
                total_score += 25
                matched_rules.append({"rule": "High-risk industry", "field": "industry", "value": entity.industry, "impact": 25})
            elif industry_lower in MEDIUM_RISK_INDUSTRIES:
                total_score += 12
                matched_rules.append({"rule": "Medium-risk industry", "field": "industry", "value": entity.industry, "impact": 12})

        # 4. Entity type risk
        if entity.entity_type.value == "company":
            total_score += 5
            matched_rules.append({"rule": "Corporate entity", "field": "entity_type", "value": "company", "impact": 5})

        # 5. Apply custom organization rules
        org_rules_result = await db.execute(
            select(RiskRule).where(
                RiskRule.organization_id == entity.organization_id,
                RiskRule.is_active == True
            )
        )
        org_rules = org_rules_result.scalars().all()
        for rule in org_rules:
            field_value = getattr(entity, rule.field, None)
            if field_value is None and entity.additional_data:
                field_value = entity.additional_data.get(rule.field)
            if field_value is not None:
                if RiskScoringService._evaluate_rule(rule, str(field_value)):
                    impact = rule.score_impact * rule.weight
                    total_score += impact
                    matched_rules.append({
                        "rule": rule.name,
                        "field": rule.field,
                        "value": str(field_value),
                        "impact": impact,
                        "rule_id": rule.id,
                    })

        # 6. Missing information penalty
        if entity.entity_type.value == "individual":
            if not entity.national_id:
                total_score += 10
                matched_rules.append({"rule": "Missing national ID", "field": "national_id", "value": None, "impact": 10})
            if not entity.date_of_birth:
                total_score += 5
                matched_rules.append({"rule": "Missing date of birth", "field": "date_of_birth", "value": None, "impact": 5})
        else:
            if not entity.registration_number:
                total_score += 10
                matched_rules.append({"rule": "Missing registration number", "field": "registration_number", "value": None, "impact": 10})

        # Determine risk level
        risk_level = RiskScoringService._score_to_level(total_score)

        # Create assessment
        assessment = RiskAssessment(
            id=generate_uuid(),
            entity_id=entity_id,
            assessed_by=user_id,
            total_score=round(total_score, 2),
            risk_level=risk_level,
            matched_rules={"rules": matched_rules, "total_rules_evaluated": len(matched_rules)},
        )
        db.add(assessment)

        # Update entity risk
        entity.risk_score = round(total_score, 2)
        entity.risk_level = RiskLevel(risk_level)
        entity.risk_factors = {"matched_rules": matched_rules}

        await db.flush()
        return assessment

    @staticmethod
    def _evaluate_rule(rule: RiskRule, field_value: str) -> bool:
        op = rule.operator
        rule_value = rule.value
        try:
            if op == "eq":
                return field_value.lower() == rule_value.lower()
            elif op == "neq":
                return field_value.lower() != rule_value.lower()
            elif op == "in":
                values = json.loads(rule_value) if rule_value.startswith("[") else rule_value.split(",")
                return field_value.lower() in [v.strip().lower() for v in values]
            elif op == "contains":
                return rule_value.lower() in field_value.lower()
            elif op == "gt":
                return float(field_value) > float(rule_value)
            elif op == "lt":
                return float(field_value) < float(rule_value)
        except (ValueError, json.JSONDecodeError):
            return False
        return False

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 60:
            return "critical"
        elif score >= 40:
            return "high"
        elif score >= 20:
            return "medium"
        return "low"
