from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.transaction import Transaction, TransactionRule, TransactionAlert, AlertStatus
from app.schemas.transaction import (
    TransactionCreate, TransactionResponse,
    TransactionRuleCreate, TransactionRuleResponse,
    TransactionAlertResponse, AlertResolution,
)
from app.services.transaction_service import TransactionMonitoringService
from app.services.audit_service import AuditService
from app.models.base import generate_uuid
from app.models.interaction import Interaction

router = APIRouter(prefix="/api/transactions", tags=["Transaction Monitoring"])


@router.post("/", response_model=TransactionResponse)
@router.post("", response_model=TransactionResponse, include_in_schema=False)
async def create_transaction(
    data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    txn = Transaction(
        id=generate_uuid(),
        entity_id=data.entity_id,
        transaction_ref=data.transaction_ref,
        transaction_type=data.transaction_type,
        amount=data.amount,
        currency=data.currency,
        counterparty_name=data.counterparty_name,
        counterparty_country=data.counterparty_country,
        description=data.description,
        transaction_date=data.transaction_date,
        metadata=data.metadata,
    )
    db.add(txn)
    await db.flush()

    # Auto-monitor
    await TransactionMonitoringService.monitor_transaction(db, txn)

    await AuditService.log(
        db, "create_transaction", "transaction", txn.id, current_user.id,
        {"amount": data.amount, "type": data.transaction_type}
    )
    return TransactionResponse.model_validate(txn)


@router.get("/", response_model=list[TransactionResponse])
@router.get("", response_model=list[TransactionResponse], include_in_schema=False)
async def list_transactions(
    entity_id: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Transaction)
    if entity_id:
        query = query.where(Transaction.entity_id == entity_id)
    query = query.offset(skip).limit(limit).order_by(Transaction.created_at.desc())
    result = await db.execute(query)
    return [TransactionResponse.model_validate(t) for t in result.scalars().all()]


@router.get("/alerts", response_model=list[TransactionAlertResponse])
async def list_alerts(
    status: str = Query(None),
    severity: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TransactionAlert)
    if status:
        query = query.where(TransactionAlert.status == AlertStatus(status))
    if severity:
        query = query.where(TransactionAlert.severity == severity)
    query = query.offset(skip).limit(limit).order_by(TransactionAlert.created_at.desc())
    result = await db.execute(query)
    return [TransactionAlertResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/alerts/{alert_id}/resolve", response_model=TransactionAlertResponse)
async def resolve_alert(
    alert_id: str,
    resolution: AlertResolution,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(TransactionAlert).where(TransactionAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = AlertStatus(resolution.status)
    alert.resolved_by = current_user.id
    alert.resolution_note = resolution.resolution_note

    interaction = Interaction(
        id=generate_uuid(),
        user_id=current_user.id,
        interaction_type="alert_resolution",
        action=f"resolve_{resolution.status}",
        resource_type="transaction_alert",
        resource_id=alert_id,
        decision=resolution.status,
        reasoning=resolution.resolution_note,
    )
    db.add(interaction)

    await db.flush()
    await AuditService.log(
        db, "resolve_alert", "transaction_alert", alert_id, current_user.id,
        {"status": resolution.status, "note": resolution.resolution_note}
    )
    return TransactionAlertResponse.model_validate(alert)


@router.post("/rules", response_model=TransactionRuleResponse)
async def create_transaction_rule(
    data: TransactionRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER]:
        raise HTTPException(status_code=403, detail="Not authorized")
    rule = TransactionRule(
        id=generate_uuid(),
        organization_id=current_user.organization_id or "",
        name=data.name,
        description=data.description,
        rule_type=data.rule_type,
        conditions=data.conditions,
        severity=data.severity,
        is_active=data.is_active,
    )
    db.add(rule)
    await db.flush()
    await AuditService.log(db, "create_transaction_rule", "transaction_rule", rule.id, current_user.id)
    return TransactionRuleResponse.model_validate(rule)


@router.get("/rules", response_model=list[TransactionRuleResponse])
async def list_transaction_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(TransactionRule)
    if current_user.organization_id:
        query = query.where(TransactionRule.organization_id == current_user.organization_id)
    result = await db.execute(query)
    return [TransactionRuleResponse.model_validate(r) for r in result.scalars().all()]
