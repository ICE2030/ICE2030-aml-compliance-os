from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.transaction import Transaction, TransactionRule, TransactionAlert, AlertSeverity, AlertStatus
from app.models.entity import Entity
from app.models.base import generate_uuid


class TransactionMonitoringService:
    @staticmethod
    async def monitor_transaction(
        db: AsyncSession,
        transaction: Transaction,
    ) -> list[TransactionAlert]:
        """Run all active rules against a transaction and generate alerts."""
        result = await db.execute(select(Entity).where(Entity.id == transaction.entity_id))
        entity = result.scalar_one_or_none()
        if not entity:
            return []

        org_id = entity.organization_id
        rules_result = await db.execute(
            select(TransactionRule).where(
                TransactionRule.organization_id == org_id,
                TransactionRule.is_active == True
            )
        )
        rules = rules_result.scalars().all()
        alerts = []

        for rule in rules:
            triggered = TransactionMonitoringService._evaluate_rule(rule, transaction)
            if triggered:
                alert = TransactionAlert(
                    id=generate_uuid(),
                    transaction_id=transaction.id,
                    rule_id=rule.id,
                    alert_type="rule_based",
                    severity=rule.severity,
                    status=AlertStatus.NEW,
                    description=f"Rule '{rule.name}' triggered: {triggered}",
                    details={"rule_conditions": rule.conditions, "trigger_reason": triggered},
                )
                db.add(alert)
                alerts.append(alert)

        # Anomaly detection: large transactions
        if transaction.amount >= 50000:
            alert = TransactionAlert(
                id=generate_uuid(),
                transaction_id=transaction.id,
                alert_type="anomaly",
                severity=AlertSeverity.HIGH if transaction.amount >= 200000 else AlertSeverity.MEDIUM,
                status=AlertStatus.NEW,
                description=f"Large transaction detected: {transaction.currency} {transaction.amount:,.2f}",
                details={"amount": transaction.amount, "threshold": 50000},
            )
            db.add(alert)
            alerts.append(alert)

        # Anomaly: high-risk country counterparty
        high_risk = ["IR", "KP", "MM", "SY", "YE", "AF"]
        if transaction.counterparty_country and transaction.counterparty_country.upper() in high_risk:
            alert = TransactionAlert(
                id=generate_uuid(),
                transaction_id=transaction.id,
                alert_type="anomaly",
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.NEW,
                description=f"Transaction with high-risk country: {transaction.counterparty_country}",
                details={"country": transaction.counterparty_country},
            )
            db.add(alert)
            alerts.append(alert)

        await db.flush()
        return alerts

    @staticmethod
    def _evaluate_rule(rule: TransactionRule, txn: Transaction) -> Optional[str]:
        conditions = rule.conditions
        rule_type = rule.rule_type

        if rule_type == "threshold":
            threshold = conditions.get("amount_threshold", 0)
            if txn.amount >= threshold:
                return f"Amount {txn.amount} exceeds threshold {threshold}"

        elif rule_type == "country":
            blocked_countries = conditions.get("countries", [])
            if txn.counterparty_country and txn.counterparty_country.upper() in [c.upper() for c in blocked_countries]:
                return f"Counterparty country {txn.counterparty_country} is restricted"

        elif rule_type == "pattern":
            keywords = conditions.get("description_keywords", [])
            if txn.description:
                for kw in keywords:
                    if kw.lower() in txn.description.lower():
                        return f"Suspicious keyword '{kw}' found in description"

        return None
