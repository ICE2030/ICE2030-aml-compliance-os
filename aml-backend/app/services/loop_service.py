"""
Reinforcing Loops Implementation:
LOOP 1: Learning Loop - capture decisions → improve suggestions
LOOP 2: Trust Loop - AI explainable suggestions → user feedback → better explanations
LOOP 3: Efficiency Loop - time tracking → bottleneck detection → workflow optimization
LOOP 4: Compliance Strength Loop - audit quality → traceability → stronger reporting
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.interaction import Interaction, LoopMetric
from app.models.case import Case, CaseStatus
from app.models.screening import ScreeningResult, MatchStatus
from app.models.audit import AuditLog
from app.models.base import generate_uuid


class LoopService:
    @staticmethod
    async def compute_learning_metrics(db: AsyncSession) -> dict:
        """LOOP 1: Learning Loop - AI suggestion accuracy and learning patterns."""
        # AI suggestion acceptance rate for screening
        total_resolved = await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.status != MatchStatus.PENDING,
                ScreeningResult.ai_suggestion.isnot(None)
            )
        )
        total = total_resolved.scalar() or 0

        correct_suggestions = await db.execute(
            select(func.count(ScreeningResult.id)).where(
                ScreeningResult.status != MatchStatus.PENDING,
                ScreeningResult.ai_suggestion.isnot(None),
                ScreeningResult.status == ScreeningResult.ai_suggestion
            )
        )
        correct = correct_suggestions.scalar() or 0

        accuracy = round(correct / total, 3) if total > 0 else 0.0

        # Case decision patterns
        case_ai_total = await db.execute(
            select(func.count(Case.id)).where(
                Case.ai_suggestion.isnot(None),
                Case.ai_suggestion_accepted.isnot(None)
            )
        )
        case_total = case_ai_total.scalar() or 0

        case_accepted = await db.execute(
            select(func.count(Case.id)).where(
                Case.ai_suggestion_accepted == True
            )
        )
        case_acc = case_accepted.scalar() or 0
        case_acceptance_rate = round(case_acc / case_total, 3) if case_total > 0 else 0.0

        metrics = {
            "screening_ai_accuracy": accuracy,
            "screening_total_resolved": total,
            "case_ai_acceptance_rate": case_acceptance_rate,
            "case_total_with_ai": case_total,
        }

        # Store metric
        metric = LoopMetric(
            id=generate_uuid(),
            loop_type="learning",
            metric_name="ai_accuracy_composite",
            metric_value=round((accuracy + case_acceptance_rate) / 2, 3),
            period="snapshot",
            period_start=datetime.now(timezone.utc).isoformat(),
            details=metrics,
        )
        db.add(metric)
        await db.flush()
        return metrics

    @staticmethod
    async def compute_trust_metrics(db: AsyncSession) -> dict:
        """LOOP 2: Trust Loop - feedback quality and explanation improvement."""
        # Get interactions with AI feedback
        feedback_result = await db.execute(
            select(Interaction).where(
                Interaction.ai_suggestion_given.isnot(None),
                Interaction.ai_suggestion_feedback.isnot(None)
            )
        )
        feedbacks = feedback_result.scalars().all()

        positive_feedback = sum(1 for f in feedbacks if f.ai_suggestion_accepted)
        total_feedback = len(feedbacks)
        trust_score = round(positive_feedback / total_feedback, 3) if total_feedback > 0 else 0.5

        metrics = {
            "trust_score": trust_score,
            "total_feedbacks": total_feedback,
            "positive_feedbacks": positive_feedback,
        }

        metric = LoopMetric(
            id=generate_uuid(),
            loop_type="trust",
            metric_name="trust_score",
            metric_value=trust_score,
            period="snapshot",
            period_start=datetime.now(timezone.utc).isoformat(),
            details=metrics,
        )
        db.add(metric)
        await db.flush()
        return metrics

    @staticmethod
    async def compute_efficiency_metrics(db: AsyncSession) -> dict:
        """LOOP 3: Efficiency Loop - time to decision, bottleneck detection."""
        # Average time to decision for cases
        cases_with_time = await db.execute(
            select(Case).where(Case.time_to_decision_minutes.isnot(None))
        )
        cases = cases_with_time.scalars().all()
        avg_time = round(sum(c.time_to_decision_minutes for c in cases) / len(cases), 1) if cases else 0

        # SLA breach rate
        total_cases = await db.execute(select(func.count(Case.id)))
        total = total_cases.scalar() or 0
        breached = await db.execute(
            select(func.count(Case.id)).where(Case.sla_breached == True)
        )
        breach_count = breached.scalar() or 0
        breach_rate = round(breach_count / total, 3) if total > 0 else 0.0

        # Bottleneck: cases by status
        status_counts = {}
        for status in CaseStatus:
            count_result = await db.execute(
                select(func.count(Case.id)).where(Case.status == status)
            )
            count = count_result.scalar() or 0
            if count > 0:
                status_counts[status.value] = count

        metrics = {
            "avg_resolution_time_minutes": avg_time,
            "sla_breach_rate": breach_rate,
            "total_cases": total,
            "breached_cases": breach_count,
            "bottlenecks": status_counts,
        }

        metric = LoopMetric(
            id=generate_uuid(),
            loop_type="efficiency",
            metric_name="efficiency_composite",
            metric_value=avg_time,
            period="snapshot",
            period_start=datetime.now(timezone.utc).isoformat(),
            details=metrics,
        )
        db.add(metric)
        await db.flush()
        return metrics

    @staticmethod
    async def compute_compliance_metrics(db: AsyncSession) -> dict:
        """LOOP 4: Compliance Strength Loop - audit quality and traceability."""
        # Total audit logs
        total_logs = await db.execute(select(func.count(AuditLog.id)))
        total = total_logs.scalar() or 0

        # Chain integrity
        chain_valid = await _check_recent_chain(db)

        # Decision traceability: cases with reasoning
        cases_with_reasoning = await db.execute(
            select(func.count(Case.id)).where(
                Case.decision.isnot(None),
                Case.decision_reasoning.isnot(None)
            )
        )
        reasoned = cases_with_reasoning.scalar() or 0

        total_decided = await db.execute(
            select(func.count(Case.id)).where(Case.decision.isnot(None))
        )
        decided = total_decided.scalar() or 0
        traceability_rate = round(reasoned / decided, 3) if decided > 0 else 1.0

        metrics = {
            "total_audit_logs": total,
            "chain_integrity": chain_valid,
            "decision_traceability_rate": traceability_rate,
            "total_decisions_with_reasoning": reasoned,
            "total_decisions": decided,
        }

        metric = LoopMetric(
            id=generate_uuid(),
            loop_type="compliance_strength",
            metric_name="compliance_score",
            metric_value=traceability_rate,
            period="snapshot",
            period_start=datetime.now(timezone.utc).isoformat(),
            details=metrics,
        )
        db.add(metric)
        await db.flush()
        return metrics

    @staticmethod
    async def get_all_loop_metrics(db: AsyncSession) -> dict:
        """Get latest metrics for all loops."""
        learning = await LoopService.compute_learning_metrics(db)
        trust = await LoopService.compute_trust_metrics(db)
        efficiency = await LoopService.compute_efficiency_metrics(db)
        compliance = await LoopService.compute_compliance_metrics(db)
        return {
            "learning_loop": learning,
            "trust_loop": trust,
            "efficiency_loop": efficiency,
            "compliance_strength_loop": compliance,
        }


async def _check_recent_chain(db: AsyncSession) -> bool:
    """Quick check on recent audit log chain."""
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
    )
    logs = list(reversed(result.scalars().all()))
    if len(logs) < 2:
        return True
    for i in range(1, len(logs)):
        if logs[i].previous_hash != logs[i - 1].entry_hash:
            return False
    return True
