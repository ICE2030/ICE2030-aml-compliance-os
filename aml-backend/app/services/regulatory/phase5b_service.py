"""Phase 5B Services: Risk Trend Dashboards + Advanced Pattern Detection.

1. ComplianceTrendService — captures point-in-time snapshots of compliance
   indicators and returns time-series data for trend dashboards.
2. AdvancedPatternService — detects patterns across obligations, controls,
   evidence gaps, and risk concentrations. All outputs are grounded in
   real stored data with full explainability.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.obligation import (
    Obligation, Control, ObligationControl, EvidenceArtifact,
    RegulatoryRisk, ObligationType, ReviewStatus, ControlType,
)
from app.models.regulatory.source import (
    Provision, RegulatoryDocument, Regulator,
)
from app.models.compliance_snapshot import ComplianceSnapshot, CompliancePattern
from app.models.base import generate_uuid

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 1. Compliance Trend Service
# ═══════════════════════════════════════════════════════════════════════

class ComplianceTrendService:
    """Captures compliance state snapshots and serves time-series trend data."""

    # Metric keys we track
    METRIC_KEYS = [
        "high_risk_obligations",
        "unmapped_obligations",
        "controls_without_evidence",
        "expired_evidence",
        "expiring_evidence",
        "review_backlog",
        "total_obligations",
        "total_controls",
        "total_evidence",
        "avg_risk_score",
        "control_coverage_pct",
        "evidence_coverage_pct",
    ]

    @staticmethod
    async def capture_snapshot(db: AsyncSession) -> dict:
        """Take a point-in-time snapshot of all compliance indicators.
        
        This is the only way trend data is created — no fabricated history.
        Each call records the current state of the compliance system.
        """
        now = datetime.now(timezone.utc)
        metrics = {}

        # Total obligations (active only)
        total_obs = (await db.execute(
            select(func.count(Obligation.id)).where(Obligation.is_active == True)
        )).scalar() or 0
        metrics["total_obligations"] = total_obs

        # Total controls
        total_controls = (await db.execute(
            select(func.count(Control.id))
        )).scalar() or 0
        metrics["total_controls"] = total_controls

        # Total evidence
        total_evidence = (await db.execute(
            select(func.count(EvidenceArtifact.id))
        )).scalar() or 0
        metrics["total_evidence"] = total_evidence

        # Unmapped obligations (no control mapping)
        mapped_ob_ids = select(ObligationControl.obligation_id).distinct()
        unmapped = (await db.execute(
            select(func.count(Obligation.id)).where(
                Obligation.is_active == True,
                Obligation.id.notin_(mapped_ob_ids),
            )
        )).scalar() or 0
        metrics["unmapped_obligations"] = unmapped

        # Controls without evidence
        controls_with_evidence = select(EvidenceArtifact.control_id).distinct()
        no_evidence = (await db.execute(
            select(func.count(Control.id)).where(
                Control.id.notin_(controls_with_evidence),
            )
        )).scalar() or 0
        metrics["controls_without_evidence"] = no_evidence

        # High-risk obligations (risk score >= 0.5)
        high_risk = (await db.execute(
            select(func.count(RegulatoryRisk.id)).where(
                RegulatoryRisk.risk_score >= 0.5,
            )
        )).scalar() or 0
        metrics["high_risk_obligations"] = high_risk

        # Expired evidence
        expired = (await db.execute(
            select(func.count(EvidenceArtifact.id)).where(
                EvidenceArtifact.expires_at < now,
                EvidenceArtifact.status == "active",
            )
        )).scalar() or 0
        metrics["expired_evidence"] = expired

        # Expiring soon (within 30 days)
        from datetime import timedelta
        expiring_cutoff = now + timedelta(days=30)
        expiring = (await db.execute(
            select(func.count(EvidenceArtifact.id)).where(
                EvidenceArtifact.expires_at >= now,
                EvidenceArtifact.expires_at <= expiring_cutoff,
                EvidenceArtifact.status == "active",
            )
        )).scalar() or 0
        metrics["expiring_evidence"] = expiring

        # Review backlog (pending obligations)
        backlog = (await db.execute(
            select(func.count(Obligation.id)).where(
                Obligation.review_status == ReviewStatus.PENDING,
                Obligation.is_active == True,
            )
        )).scalar() or 0
        metrics["review_backlog"] = backlog

        # Average risk score
        avg_risk = (await db.execute(
            select(func.avg(RegulatoryRisk.risk_score)).where(
                RegulatoryRisk.risk_score.isnot(None),
            )
        )).scalar()
        metrics["avg_risk_score"] = round(avg_risk, 4) if avg_risk else 0.0

        # Coverage percentages
        metrics["control_coverage_pct"] = round(
            ((total_obs - unmapped) / total_obs * 100) if total_obs > 0 else 0.0, 1
        )
        evidence_covered_controls = (await db.execute(
            select(func.count(func.distinct(EvidenceArtifact.control_id)))
        )).scalar() or 0
        metrics["evidence_coverage_pct"] = round(
            (evidence_covered_controls / total_controls * 100) if total_controls > 0 else 0.0, 1
        )

        # Build breakdown by regulator
        regulator_breakdown = await ComplianceTrendService._breakdown_by_regulator(db)

        # Persist snapshots
        snapshots_created = 0
        for key, value in metrics.items():
            snapshot = ComplianceSnapshot(
                id=generate_uuid(),
                snapshot_date=now,
                metric_key=key,
                metric_value=float(value),
                breakdown=regulator_breakdown.get(key),
            )
            db.add(snapshot)
            snapshots_created += 1

        return {
            "snapshot_date": now.isoformat(),
            "metrics": metrics,
            "snapshots_created": snapshots_created,
        }

    @staticmethod
    async def _breakdown_by_regulator(db: AsyncSession) -> dict:
        """Get per-regulator breakdown for key metrics."""
        breakdown = {}

        # High-risk by regulator
        result = await db.execute(
            select(
                Regulator.abbreviation,
                func.count(RegulatoryRisk.id),
            )
            .select_from(RegulatoryRisk)
            .join(Obligation, RegulatoryRisk.obligation_id == Obligation.id)
            .join(Provision, Obligation.provision_id == Provision.id)
            .join(RegulatoryDocument, Provision.document_id == RegulatoryDocument.id)
            .join(Regulator, RegulatoryDocument.regulator_id == Regulator.id)
            .where(RegulatoryRisk.risk_score >= 0.5)
            .group_by(Regulator.abbreviation)
        )
        high_risk_by_reg = {row[0]: row[1] for row in result.all()}
        if high_risk_by_reg:
            breakdown["high_risk_obligations"] = high_risk_by_reg

        # Unmapped by regulator
        mapped_ids = select(ObligationControl.obligation_id).distinct()
        result = await db.execute(
            select(
                Regulator.abbreviation,
                func.count(Obligation.id),
            )
            .select_from(Obligation)
            .join(Provision, Obligation.provision_id == Provision.id)
            .join(RegulatoryDocument, Provision.document_id == RegulatoryDocument.id)
            .join(Regulator, RegulatoryDocument.regulator_id == Regulator.id)
            .where(
                Obligation.is_active == True,
                Obligation.id.notin_(mapped_ids),
            )
            .group_by(Regulator.abbreviation)
        )
        unmapped_by_reg = {row[0]: row[1] for row in result.all()}
        if unmapped_by_reg:
            breakdown["unmapped_obligations"] = unmapped_by_reg

        return breakdown

    @staticmethod
    async def get_trends(
        db: AsyncSession,
        metric_key: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        """Return time-series trend data for compliance indicators.
        
        If metric_key is specified, returns only that metric's history.
        Otherwise returns the latest snapshot for each metric plus
        recent history for charting.
        """
        if metric_key:
            result = await db.execute(
                select(ComplianceSnapshot)
                .where(ComplianceSnapshot.metric_key == metric_key)
                .order_by(ComplianceSnapshot.snapshot_date.desc())
                .limit(limit)
            )
            snapshots = list(result.scalars().all())
            return {
                "metric_key": metric_key,
                "data_points": [
                    {
                        "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                        "value": s.metric_value,
                        "breakdown": s.breakdown,
                    }
                    for s in reversed(snapshots)  # chronological order
                ],
                "count": len(snapshots),
            }

        # All metrics: latest snapshot for each + recent history
        latest = {}
        history = defaultdict(list)

        for key in ComplianceTrendService.METRIC_KEYS:
            result = await db.execute(
                select(ComplianceSnapshot)
                .where(ComplianceSnapshot.metric_key == key)
                .order_by(ComplianceSnapshot.snapshot_date.desc())
                .limit(limit)
            )
            snapshots = list(result.scalars().all())
            if snapshots:
                latest[key] = {
                    "value": snapshots[0].metric_value,
                    "date": snapshots[0].snapshot_date.isoformat() if snapshots[0].snapshot_date else None,
                    "breakdown": snapshots[0].breakdown,
                }
                for s in reversed(snapshots):
                    history[key].append({
                        "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                        "value": s.metric_value,
                    })

        return {
            "latest": latest,
            "history": dict(history),
            "metric_keys": ComplianceTrendService.METRIC_KEYS,
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. Advanced Pattern Detection Service
# ═══════════════════════════════════════════════════════════════════════

class AdvancedPatternService:
    """Detects compliance patterns across obligations, controls, evidence,
    and risk data. All patterns are grounded in real stored data."""

    @staticmethod
    async def detect_all_patterns(db: AsyncSession) -> list[dict]:
        """Run all pattern detection algorithms and persist results."""
        # Deactivate old patterns before re-detection
        old_patterns = await db.execute(
            select(CompliancePattern).where(CompliancePattern.is_active == True)
        )
        for p in old_patterns.scalars().all():
            p.is_active = False

        patterns = []
        patterns.extend(await AdvancedPatternService._detect_control_risk_associations(db))
        patterns.extend(await AdvancedPatternService._detect_persistent_evidence_gaps(db))
        patterns.extend(await AdvancedPatternService._detect_recurring_control_weaknesses(db))
        patterns.extend(await AdvancedPatternService._detect_obligation_type_risk_clusters(db))
        patterns.extend(await AdvancedPatternService._detect_regulator_risk_concentration(db))

        return patterns

    @staticmethod
    async def _detect_control_risk_associations(db: AsyncSession) -> list[dict]:
        """Find control types repeatedly associated with high-risk obligations."""
        now = datetime.now(timezone.utc)
        patterns = []

        # Get high-risk obligations (score >= 0.5) that have controls
        result = await db.execute(
            select(
                Control.control_type,
                func.count(func.distinct(RegulatoryRisk.obligation_id)).label("high_risk_count"),
            )
            .select_from(RegulatoryRisk)
            .join(Obligation, RegulatoryRisk.obligation_id == Obligation.id)
            .join(ObligationControl, ObligationControl.obligation_id == Obligation.id)
            .join(Control, ObligationControl.control_id == Control.id)
            .where(RegulatoryRisk.risk_score >= 0.5)
            .group_by(Control.control_type)
            .having(func.count(func.distinct(RegulatoryRisk.obligation_id)) >= 2)
        )
        clusters = result.all()

        for row in clusters:
            ct_val = row[0].value if hasattr(row[0], 'value') else str(row[0])
            count = row[1]

            # Get total obligations for this control type
            total_for_type = (await db.execute(
                select(func.count(func.distinct(ObligationControl.obligation_id)))
                .join(Control, ObligationControl.control_id == Control.id)
                .where(Control.control_type == row[0])
            )).scalar() or 1

            pct = round(count / total_for_type * 100, 1)

            # Only report if >= 40% of obligations for this type are high-risk
            if pct < 40:
                continue

            severity = "high" if pct >= 70 else "medium"
            confidence = min(0.9, 0.5 + (count / 20))

            pattern = CompliancePattern(
                id=generate_uuid(),
                pattern_type="control_risk_association",
                title=f"{ct_val.title()} controls have {pct}% high-risk obligation rate",
                title_ar=f"ضوابط {ct_val} لديها معدل التزامات عالية المخاطر بنسبة {pct}%",
                description=(
                    f"Control type '{ct_val}' is associated with {count} high-risk obligations "
                    f"out of {total_for_type} total ({pct}%). This suggests the control type "
                    f"may need strengthening or additional mitigating measures."
                ),
                description_ar=(
                    f"نوع الضابط '{ct_val}' مرتبط بـ {count} التزام عالي المخاطر "
                    f"من إجمالي {total_for_type} ({pct}%). هذا يشير إلى أن نوع الضابط "
                    f"قد يحتاج إلى تعزيز أو إجراءات تخفيف إضافية."
                ),
                severity=severity,
                confidence=round(confidence, 2),
                affected_items={"control_type": ct_val, "high_risk_obligation_count": count},
                pattern_data={
                    "control_type": ct_val,
                    "high_risk_count": count,
                    "total_for_type": total_for_type,
                    "high_risk_pct": pct,
                },
                recommendation=(
                    f"Review all {ct_val} controls covering high-risk obligations. "
                    f"Consider supplementing with additional control types or increasing "
                    f"monitoring frequency."
                ),
                recommendation_ar=(
                    f"مراجعة جميع ضوابط {ct_val} التي تغطي الالتزامات عالية المخاطر. "
                    f"النظر في إضافة أنواع ضوابط إضافية أو زيادة تكرار المراقبة."
                ),
                is_active=True,
                last_detected=now,
            )
            db.add(pattern)
            patterns.append(AdvancedPatternService._serialize_pattern(pattern))

        return patterns

    @staticmethod
    async def _detect_persistent_evidence_gaps(db: AsyncSession) -> list[dict]:
        """Find topics/regulators with persistent evidence gaps."""
        now = datetime.now(timezone.utc)
        patterns = []

        # Controls without any evidence, grouped by regulator
        controls_with_ev = select(EvidenceArtifact.control_id).distinct()
        result = await db.execute(
            select(
                Regulator.abbreviation,
                Regulator.name,
                func.count(Control.id).label("no_evidence_count"),
            )
            .select_from(Control)
            .join(ObligationControl, ObligationControl.control_id == Control.id)
            .join(Obligation, ObligationControl.obligation_id == Obligation.id)
            .join(Provision, Obligation.provision_id == Provision.id)
            .join(RegulatoryDocument, Provision.document_id == RegulatoryDocument.id)
            .join(Regulator, RegulatoryDocument.regulator_id == Regulator.id)
            .where(Control.id.notin_(controls_with_ev))
            .group_by(Regulator.abbreviation, Regulator.name)
            .having(func.count(Control.id) >= 1)
        )
        gaps = result.all()

        for row in gaps:
            abbr, name, count = row[0], row[1], row[2]

            # Get total controls for this regulator
            total_controls = (await db.execute(
                select(func.count(func.distinct(Control.id)))
                .select_from(Control)
                .join(ObligationControl, ObligationControl.control_id == Control.id)
                .join(Obligation, ObligationControl.obligation_id == Obligation.id)
                .join(Provision, Obligation.provision_id == Provision.id)
                .join(RegulatoryDocument, Provision.document_id == RegulatoryDocument.id)
                .join(Regulator, RegulatoryDocument.regulator_id == Regulator.id)
                .where(Regulator.abbreviation == abbr)
            )).scalar() or 1

            gap_pct = round(count / total_controls * 100, 1)
            if gap_pct < 30:
                continue

            severity = "critical" if gap_pct >= 80 else ("high" if gap_pct >= 60 else "medium")
            confidence = min(0.95, 0.6 + (count / 15))

            pattern = CompliancePattern(
                id=generate_uuid(),
                pattern_type="persistent_evidence_gap",
                title=f"{abbr}: {gap_pct}% of controls lack evidence ({count}/{total_controls})",
                title_ar=f"{abbr}: {gap_pct}% من الضوابط تفتقر إلى أدلة ({count}/{total_controls})",
                description=(
                    f"Regulator '{name}' ({abbr}) has {count} controls out of {total_controls} "
                    f"with no supporting evidence ({gap_pct}%). This represents a persistent "
                    f"evidence collection gap that should be prioritized."
                ),
                description_ar=(
                    f"الجهة التنظيمية '{name}' ({abbr}) لديها {count} ضابط من {total_controls} "
                    f"بدون أدلة داعمة ({gap_pct}%). يمثل هذا فجوة مستمرة في جمع الأدلة."
                ),
                severity=severity,
                confidence=round(confidence, 2),
                affected_items={"regulator": abbr, "controls_without_evidence": count},
                pattern_data={
                    "regulator_abbr": abbr,
                    "regulator_name": name,
                    "no_evidence_count": count,
                    "total_controls": total_controls,
                    "gap_pct": gap_pct,
                },
                recommendation=(
                    f"Prioritize evidence collection for {abbr} controls. "
                    f"Focus on the {count} controls currently lacking evidence artifacts."
                ),
                recommendation_ar=(
                    f"إعطاء الأولوية لجمع الأدلة لضوابط {abbr}. "
                    f"التركيز على {count} ضابط يفتقر حالياً إلى أدلة."
                ),
                is_active=True,
                last_detected=now,
            )
            db.add(pattern)
            patterns.append(AdvancedPatternService._serialize_pattern(pattern))

        return patterns

    @staticmethod
    async def _detect_recurring_control_weaknesses(db: AsyncSession) -> list[dict]:
        """Find regulators/topics with recurring control weaknesses."""
        now = datetime.now(timezone.utc)
        patterns = []

        # Obligations with high-risk scores AND no controls (double weakness)
        mapped_ids = select(ObligationControl.obligation_id).distinct()
        result = await db.execute(
            select(
                Regulator.abbreviation,
                Regulator.name,
                func.count(Obligation.id).label("weak_count"),
            )
            .select_from(Obligation)
            .join(Provision, Obligation.provision_id == Provision.id)
            .join(RegulatoryDocument, Provision.document_id == RegulatoryDocument.id)
            .join(Regulator, RegulatoryDocument.regulator_id == Regulator.id)
            .join(RegulatoryRisk, RegulatoryRisk.obligation_id == Obligation.id)
            .where(
                Obligation.is_active == True,
                Obligation.id.notin_(mapped_ids),
                RegulatoryRisk.risk_score >= 0.5,
            )
            .group_by(Regulator.abbreviation, Regulator.name)
            .having(func.count(Obligation.id) >= 1)
        )
        weaknesses = result.all()

        for row in weaknesses:
            abbr, name, count = row[0], row[1], row[2]
            severity = "critical" if count >= 5 else ("high" if count >= 3 else "medium")
            confidence = min(0.9, 0.5 + (count / 10))

            pattern = CompliancePattern(
                id=generate_uuid(),
                pattern_type="recurring_control_weakness",
                title=f"{abbr}: {count} high-risk obligations with no controls",
                title_ar=f"{abbr}: {count} التزام عالي المخاطر بدون ضوابط",
                description=(
                    f"Regulator '{name}' ({abbr}) has {count} obligations that are both "
                    f"high-risk (score ≥ 0.5) and unmapped to any control. This double "
                    f"exposure represents a recurring control weakness."
                ),
                description_ar=(
                    f"الجهة التنظيمية '{name}' ({abbr}) لديها {count} التزام عالي المخاطر "
                    f"وغير مرتبط بأي ضابط. هذا التعرض المزدوج يمثل ضعف متكرر في الضوابط."
                ),
                severity=severity,
                confidence=round(confidence, 2),
                affected_items={"regulator": abbr, "unmapped_high_risk_count": count},
                pattern_data={
                    "regulator_abbr": abbr,
                    "regulator_name": name,
                    "unmapped_high_risk_count": count,
                },
                recommendation=(
                    f"Immediately map controls to the {count} high-risk unmapped obligations "
                    f"under {abbr}. This is a critical compliance gap."
                ),
                recommendation_ar=(
                    f"ربط الضوابط فوراً بـ {count} التزام عالي المخاطر غير المربوط "
                    f"تحت {abbr}. هذه فجوة امتثال حرجة."
                ),
                is_active=True,
                last_detected=now,
            )
            db.add(pattern)
            patterns.append(AdvancedPatternService._serialize_pattern(pattern))

        return patterns

    @staticmethod
    async def _detect_obligation_type_risk_clusters(db: AsyncSession) -> list[dict]:
        """Find obligation types that cluster at high risk."""
        now = datetime.now(timezone.utc)
        patterns = []

        result = await db.execute(
            select(
                Obligation.obligation_type,
                func.count(Obligation.id).label("total"),
                func.sum(
                    case(
                        (RegulatoryRisk.risk_score >= 0.5, 1),
                        else_=0,
                    )
                ).label("high_risk_count"),
                func.avg(RegulatoryRisk.risk_score).label("avg_score"),
            )
            .select_from(Obligation)
            .join(RegulatoryRisk, RegulatoryRisk.obligation_id == Obligation.id)
            .where(Obligation.is_active == True)
            .group_by(Obligation.obligation_type)
            .having(func.count(Obligation.id) >= 2)
        )
        clusters = result.all()

        for row in clusters:
            ob_type = row[0].value if hasattr(row[0], 'value') else str(row[0])
            total = row[1]
            high_risk = row[2] or 0
            avg_score = row[3] or 0

            if total == 0:
                continue
            pct = round(high_risk / total * 100, 1)
            if pct < 50:
                continue

            severity = "high" if pct >= 75 else "medium"
            confidence = min(0.85, 0.4 + (total / 20))

            pattern = CompliancePattern(
                id=generate_uuid(),
                pattern_type="obligation_type_risk_cluster",
                title=f"'{ob_type}' obligations: {pct}% are high-risk (avg score {round(avg_score, 2)})",
                title_ar=f"التزامات '{ob_type}': {pct}% عالية المخاطر (متوسط الدرجة {round(avg_score, 2)})",
                description=(
                    f"Obligation type '{ob_type}' has {high_risk} out of {total} obligations "
                    f"scoring as high-risk ({pct}%), with an average risk score of "
                    f"{round(avg_score, 2)}. This concentration suggests systemic exposure."
                ),
                description_ar=(
                    f"نوع الالتزام '{ob_type}' لديه {high_risk} من {total} التزام "
                    f"بتصنيف عالي المخاطر ({pct}%)، بمتوسط درجة مخاطر {round(avg_score, 2)}."
                ),
                severity=severity,
                confidence=round(confidence, 2),
                affected_items={"obligation_type": ob_type, "high_risk_count": high_risk},
                pattern_data={
                    "obligation_type": ob_type,
                    "total": total,
                    "high_risk_count": high_risk,
                    "high_risk_pct": pct,
                    "avg_risk_score": round(avg_score, 4),
                },
                recommendation=(
                    f"Review risk mitigation strategy for all '{ob_type}' obligations. "
                    f"Consider adding dedicated controls or increasing monitoring."
                ),
                recommendation_ar=(
                    f"مراجعة استراتيجية تخفيف المخاطر لجميع التزامات '{ob_type}'. "
                    f"النظر في إضافة ضوابط مخصصة أو زيادة المراقبة."
                ),
                is_active=True,
                last_detected=now,
            )
            db.add(pattern)
            patterns.append(AdvancedPatternService._serialize_pattern(pattern))

        return patterns

    @staticmethod
    async def _detect_regulator_risk_concentration(db: AsyncSession) -> list[dict]:
        """Find regulators with disproportionate high-risk concentrations."""
        now = datetime.now(timezone.utc)
        patterns = []

        result = await db.execute(
            select(
                Regulator.abbreviation,
                Regulator.name,
                func.count(RegulatoryRisk.id).label("total_risks"),
                func.sum(
                    case(
                        (RegulatoryRisk.risk_score >= 0.5, 1),
                        else_=0,
                    )
                ).label("high_risk_count"),
                func.avg(RegulatoryRisk.risk_score).label("avg_score"),
            )
            .select_from(RegulatoryRisk)
            .join(Obligation, RegulatoryRisk.obligation_id == Obligation.id)
            .join(Provision, Obligation.provision_id == Provision.id)
            .join(RegulatoryDocument, Provision.document_id == RegulatoryDocument.id)
            .join(Regulator, RegulatoryDocument.regulator_id == Regulator.id)
            .group_by(Regulator.abbreviation, Regulator.name)
            .having(func.count(RegulatoryRisk.id) >= 2)
        )
        concentrations = result.all()

        for row in concentrations:
            abbr, name, total, high_risk, avg_score = row[0], row[1], row[2], row[3] or 0, row[4] or 0
            if total == 0:
                continue
            pct = round(high_risk / total * 100, 1)
            if pct < 40:
                continue

            severity = "critical" if pct >= 80 else ("high" if pct >= 60 else "medium")
            confidence = min(0.9, 0.5 + (total / 25))

            pattern = CompliancePattern(
                id=generate_uuid(),
                pattern_type="regulator_risk_concentration",
                title=f"{abbr}: {pct}% high-risk rate ({high_risk}/{total} obligations)",
                title_ar=f"{abbr}: معدل مخاطر عالية {pct}% ({high_risk}/{total} التزام)",
                description=(
                    f"Regulator '{name}' ({abbr}) has {high_risk} out of {total} scored "
                    f"obligations in the high-risk category ({pct}%), with an average risk "
                    f"score of {round(avg_score, 2)}. This concentration may indicate "
                    f"insufficient controls for this regulator's requirements."
                ),
                description_ar=(
                    f"الجهة التنظيمية '{name}' ({abbr}) لديها {high_risk} من {total} التزام "
                    f"مقيّم في فئة المخاطر العالية ({pct}%)، بمتوسط درجة {round(avg_score, 2)}."
                ),
                severity=severity,
                confidence=round(confidence, 2),
                affected_items={"regulator": abbr, "high_risk_count": high_risk},
                pattern_data={
                    "regulator_abbr": abbr,
                    "regulator_name": name,
                    "total_risks": total,
                    "high_risk_count": high_risk,
                    "high_risk_pct": pct,
                    "avg_risk_score": round(avg_score, 4),
                },
                recommendation=(
                    f"Conduct a focused review of {abbr} compliance controls. "
                    f"Prioritize the {high_risk} high-risk obligations for immediate mitigation."
                ),
                recommendation_ar=(
                    f"إجراء مراجعة مركزة لضوابط الامتثال لـ {abbr}. "
                    f"إعطاء الأولوية لـ {high_risk} التزام عالي المخاطر للتخفيف الفوري."
                ),
                is_active=True,
                last_detected=now,
            )
            db.add(pattern)
            patterns.append(AdvancedPatternService._serialize_pattern(pattern))

        return patterns

    @staticmethod
    async def get_active_patterns(
        db: AsyncSession,
        pattern_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[dict]:
        """Return all active compliance patterns, optionally filtered."""
        query = select(CompliancePattern).where(CompliancePattern.is_active == True)
        if pattern_type:
            query = query.where(CompliancePattern.pattern_type == pattern_type)
        if severity:
            query = query.where(CompliancePattern.severity == severity)
        query = query.order_by(CompliancePattern.last_detected.desc())

        result = await db.execute(query)
        return [
            AdvancedPatternService._serialize_pattern(p)
            for p in result.scalars().all()
        ]

    @staticmethod
    def _serialize_pattern(p: CompliancePattern) -> dict:
        return {
            "id": p.id,
            "pattern_type": p.pattern_type,
            "title": p.title,
            "title_ar": p.title_ar,
            "description": p.description,
            "description_ar": p.description_ar,
            "severity": p.severity,
            "confidence": p.confidence,
            "affected_items": p.affected_items,
            "pattern_data": p.pattern_data,
            "recommendation": p.recommendation,
            "recommendation_ar": p.recommendation_ar,
            "is_active": p.is_active,
            "last_detected": p.last_detected.isoformat() if p.last_detected else None,
        }
