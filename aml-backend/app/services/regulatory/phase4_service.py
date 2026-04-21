"""Phase 4 Services: Control Mapping, Evidence, Risk Scoring, Gap Analysis, Executive Reporting.

Implements the full chain: Source -> Provision -> Obligation -> Control -> Evidence -> Risk -> Action
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.obligation import (
    Obligation, Control, ObligationControl, EvidenceArtifact,
    RegulatoryRisk, RegulatoryAction,
    ControlType, ControlStatus, ReviewStatus, ObligationType,
    RiskType, ActionType, ActionStatus,
)
from app.models.regulatory.source import (
    Provision, RegulatoryDocument, Regulator, Jurisdiction, Source, SourceVersion,
)
from app.models.base import generate_uuid

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 1. Control Mapping Service
# ═══════════════════════════════════════════════════════════════════════

class ControlMappingService:
    """CRUD + mapping for controls and obligation-control relationships."""

    @staticmethod
    async def create_control(
        db: AsyncSession,
        name: str,
        control_type: str,
        description: str = None,
        name_ar: str = None,
        description_ar: str = None,
        owner: str = None,
        frequency: str = None,
        status: str = "draft",
        regulator_id: str = None,
        source_id: str = None,
    ) -> Control:
        control = Control(
            id=generate_uuid(),
            name=name,
            name_ar=name_ar,
            description=description,
            description_ar=description_ar,
            control_type=ControlType(control_type),
            owner=owner,
            frequency=frequency,
            status=ControlStatus(status),
            regulator_id=regulator_id,
            source_id=source_id,
        )
        db.add(control)
        await db.flush()
        return control

    @staticmethod
    async def update_control(
        db: AsyncSession,
        control_id: str,
        **kwargs,
    ) -> Optional[Control]:
        control = await db.get(Control, control_id)
        if not control:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(control, key):
                if key == "control_type":
                    value = ControlType(value)
                elif key == "status":
                    value = ControlStatus(value)
                setattr(control, key, value)
        await db.flush()
        return control

    @staticmethod
    async def delete_control(db: AsyncSession, control_id: str) -> bool:
        control = await db.get(Control, control_id)
        if not control:
            return False
        await db.delete(control)
        await db.flush()
        return True

    @staticmethod
    async def get_control(db: AsyncSession, control_id: str) -> Optional[dict]:
        control = await db.get(Control, control_id)
        if not control:
            return None
        return await ControlMappingService._serialize_control(db, control)

    @staticmethod
    async def list_controls(
        db: AsyncSession,
        control_type: str = None,
        status: str = None,
        owner: str = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        query = select(Control)
        count_query = select(func.count(Control.id))

        if control_type:
            query = query.where(Control.control_type == ControlType(control_type))
            count_query = count_query.where(Control.control_type == ControlType(control_type))
        if status:
            query = query.where(Control.status == ControlStatus(status))
            count_query = count_query.where(Control.status == ControlStatus(status))
        if owner:
            query = query.where(Control.owner == owner)
            count_query = count_query.where(Control.owner == owner)

        total = (await db.execute(count_query)).scalar() or 0
        result = await db.execute(query.offset(skip).limit(limit).order_by(Control.created_at.desc()))
        controls = list(result.scalars().all())

        items = []
        for c in controls:
            items.append(await ControlMappingService._serialize_control(db, c))
        return items, total

    @staticmethod
    async def map_obligation_to_control(
        db: AsyncSession,
        obligation_id: str,
        control_id: str,
        mapping_confidence: float = 1.0,
        mapping_method: str = "manual",
        notes: str = None,
    ) -> Optional[dict]:
        ob = await db.get(Obligation, obligation_id)
        ctrl = await db.get(Control, control_id)
        if not ob or not ctrl:
            return None

        existing = await db.execute(
            select(ObligationControl).where(
                ObligationControl.obligation_id == obligation_id,
                ObligationControl.control_id == control_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "Mapping already exists"}

        mapping = ObligationControl(
            obligation_id=obligation_id,
            control_id=control_id,
            mapping_confidence=mapping_confidence,
            mapping_method=mapping_method,
            notes=notes,
        )
        db.add(mapping)
        await db.flush()
        return {
            "obligation_id": obligation_id,
            "control_id": control_id,
            "mapping_confidence": mapping_confidence,
            "mapping_method": mapping_method,
            "notes": notes,
        }

    @staticmethod
    async def unmap_obligation_from_control(
        db: AsyncSession,
        obligation_id: str,
        control_id: str,
    ) -> bool:
        result = await db.execute(
            select(ObligationControl).where(
                ObligationControl.obligation_id == obligation_id,
                ObligationControl.control_id == control_id,
            )
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            return False
        await db.delete(mapping)
        await db.flush()
        return True

    @staticmethod
    async def get_control_obligations(db: AsyncSession, control_id: str) -> list[dict]:
        result = await db.execute(
            select(ObligationControl).where(ObligationControl.control_id == control_id)
        )
        mappings = list(result.scalars().all())
        items = []
        for m in mappings:
            ob = await db.get(Obligation, m.obligation_id)
            if ob:
                ot = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
                rs = ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status)
                items.append({
                    "obligation_id": ob.id,
                    "text": ob.text,
                    "obligation_type": ot,
                    "review_status": rs,
                    "confidence": ob.confidence,
                    "mapping_confidence": m.mapping_confidence,
                    "mapping_method": m.mapping_method,
                })
        return items

    @staticmethod
    async def _serialize_control(db: AsyncSession, control: Control) -> dict:
        ob_count = (await db.execute(
            select(func.count(ObligationControl.obligation_id)).where(
                ObligationControl.control_id == control.id
            )
        )).scalar() or 0

        ev_count = (await db.execute(
            select(func.count(EvidenceArtifact.id)).where(
                EvidenceArtifact.control_id == control.id
            )
        )).scalar() or 0

        ct = control.control_type.value if hasattr(control.control_type, 'value') else str(control.control_type)
        st = control.status.value if hasattr(control.status, 'value') else str(control.status)

        return {
            "id": control.id,
            "name": control.name,
            "name_ar": control.name_ar,
            "description": control.description,
            "description_ar": control.description_ar,
            "control_type": ct,
            "owner": control.owner,
            "frequency": control.frequency,
            "status": st,
            "effectiveness_rating": control.effectiveness_rating,
            "last_tested": str(control.last_tested) if control.last_tested else None,
            "test_frequency": control.test_frequency,
            "regulator_id": control.regulator_id,
            "source_id": control.source_id,
            "obligation_count": ob_count,
            "evidence_count": ev_count,
            "created_at": str(control.created_at) if control.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. Evidence Mapping Service
# ═══════════════════════════════════════════════════════════════════════

class EvidenceMappingService:
    """CRUD for evidence artifacts linked to controls."""

    @staticmethod
    async def create_evidence(
        db: AsyncSession,
        control_id: str,
        name: str,
        artifact_type: str,
        description: str = None,
        name_ar: str = None,
        description_ar: str = None,
        source_system: str = None,
        collection_method: str = None,
        periodicity: str = None,
        owner: str = None,
        status: str = "active",
    ) -> Optional[EvidenceArtifact]:
        ctrl = await db.get(Control, control_id)
        if not ctrl:
            return None
        ev = EvidenceArtifact(
            id=generate_uuid(),
            control_id=control_id,
            name=name,
            name_ar=name_ar,
            artifact_type=artifact_type,
            description=description,
            description_ar=description_ar,
            source_system=source_system,
            collection_method=collection_method,
            periodicity=periodicity,
            owner=owner,
            status=status,
            collected_at=datetime.now(timezone.utc),
        )
        db.add(ev)
        await db.flush()
        return ev

    @staticmethod
    async def update_evidence(db: AsyncSession, evidence_id: str, **kwargs) -> Optional[EvidenceArtifact]:
        ev = await db.get(EvidenceArtifact, evidence_id)
        if not ev:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(ev, key):
                setattr(ev, key, value)
        await db.flush()
        return ev

    @staticmethod
    async def delete_evidence(db: AsyncSession, evidence_id: str) -> bool:
        ev = await db.get(EvidenceArtifact, evidence_id)
        if not ev:
            return False
        await db.delete(ev)
        await db.flush()
        return True

    @staticmethod
    async def get_evidence(db: AsyncSession, evidence_id: str) -> Optional[dict]:
        ev = await db.get(EvidenceArtifact, evidence_id)
        if not ev:
            return None
        return EvidenceMappingService._serialize_evidence(ev)

    @staticmethod
    async def list_evidence(
        db: AsyncSession,
        control_id: str = None,
        artifact_type: str = None,
        status: str = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        query = select(EvidenceArtifact)
        count_query = select(func.count(EvidenceArtifact.id))

        if control_id:
            query = query.where(EvidenceArtifact.control_id == control_id)
            count_query = count_query.where(EvidenceArtifact.control_id == control_id)
        if artifact_type:
            query = query.where(EvidenceArtifact.artifact_type == artifact_type)
            count_query = count_query.where(EvidenceArtifact.artifact_type == artifact_type)
        if status:
            query = query.where(EvidenceArtifact.status == status)
            count_query = count_query.where(EvidenceArtifact.status == status)

        total = (await db.execute(count_query)).scalar() or 0
        result = await db.execute(query.offset(skip).limit(limit).order_by(EvidenceArtifact.created_at.desc()))
        items = [EvidenceMappingService._serialize_evidence(e) for e in result.scalars().all()]
        return items, total

    @staticmethod
    async def get_evidence_chain(db: AsyncSession, evidence_id: str) -> Optional[dict]:
        """Trace evidence back through: Evidence -> Control -> Obligation -> Provision -> Source."""
        ev = await db.get(EvidenceArtifact, evidence_id)
        if not ev:
            return None

        control = await db.get(Control, ev.control_id)
        chain = {
            "evidence": EvidenceMappingService._serialize_evidence(ev),
            "control": None,
            "obligations": [],
            "provisions": [],
            "sources": [],
        }
        if control:
            ct = control.control_type.value if hasattr(control.control_type, 'value') else str(control.control_type)
            chain["control"] = {"id": control.id, "name": control.name, "control_type": ct}

            oc_result = await db.execute(
                select(ObligationControl).where(ObligationControl.control_id == control.id)
            )
            for oc in oc_result.scalars().all():
                ob = await db.get(Obligation, oc.obligation_id)
                if not ob:
                    continue
                ot = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
                ob_chain = {"obligation_id": ob.id, "text": ob.text, "obligation_type": ot}
                prov = await db.get(Provision, ob.provision_id)
                if prov:
                    ob_chain["provision"] = {"id": prov.id, "section_number": prov.section_number, "title": prov.title}
                    chain["provisions"].append({
                        "id": prov.id,
                        "title": prov.title,
                        "article_number": prov.section_number,
                    })
                    doc = await db.get(RegulatoryDocument, prov.document_id)
                    if doc:
                        reg = await db.get(Regulator, doc.regulator_id)
                        ob_chain["source"] = {
                            "document_title": doc.title,
                            "regulator": reg.abbreviation if reg else None,
                        }
                        chain["sources"].append({
                            "id": doc.id,
                            "title": doc.title,
                            "regulator": reg.abbreviation if reg else None,
                        })
                chain["obligations"].append(ob_chain)

        return chain

    @staticmethod
    def _serialize_evidence(ev: EvidenceArtifact) -> dict:
        return {
            "id": ev.id,
            "control_id": ev.control_id,
            "name": ev.name,
            "name_ar": ev.name_ar,
            "artifact_type": ev.artifact_type,
            "description": ev.description,
            "description_ar": ev.description_ar,
            "source_system": ev.source_system,
            "collection_method": ev.collection_method,
            "periodicity": ev.periodicity,
            "owner": ev.owner,
            "status": ev.status,
            "collected_at": str(ev.collected_at) if ev.collected_at else None,
            "expires_at": str(ev.expires_at) if ev.expires_at else None,
            "created_at": str(ev.created_at) if ev.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. Risk Scoring Service
# ═══════════════════════════════════════════════════════════════════════

_AUTHORITY_WEIGHTS = {"tier_1": 1.0, "tier_2": 0.7, "tier_3": 0.4, "tier_4": 0.2}
_BINDING_WEIGHT = 0.15
_CRITICALITY_WEIGHTS = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
_OBLIGATION_TYPE_CRITICALITY = {
    "mandatory": "high", "prohibition": "high", "reporting": "high",
    "threshold": "medium", "identification": "medium", "verification": "medium",
    "ongoing_monitoring": "medium", "recordkeeping": "medium",
    "governance": "medium", "deadline": "medium",
    "penalty": "critical", "definition": "low", "guidance": "low",
}
_SEVERITY_MAP = [
    (0.0, 0.25, "low", "unlikely"),
    (0.25, 0.50, "medium", "possible"),
    (0.50, 0.75, "high", "likely"),
    (0.75, 1.01, "critical", "almost_certain"),
]


class RiskScoringService:
    """Transparent, explainable risk scoring for obligations."""

    @staticmethod
    async def score_obligation(db: AsyncSession, obligation_id: str) -> Optional[dict]:
        """Compute risk score for a single obligation. Returns factor breakdown."""
        ob = await db.get(Obligation, obligation_id)
        if not ob:
            return None

        factors = {}

        # Factor 1: Authority level of source
        authority_score = 0.5
        provision = await db.get(Provision, ob.provision_id)
        regulator_abbr = None
        if provision:
            doc = await db.get(RegulatoryDocument, provision.document_id)
            if doc:
                reg = await db.get(Regulator, doc.regulator_id)
                if reg:
                    regulator_abbr = reg.abbreviation
                if doc.source_version_id:
                    sv = await db.get(SourceVersion, doc.source_version_id)
                    if sv:
                        src = await db.get(Source, sv.source_id)
                        if src:
                            al = src.authority_level.value if hasattr(src.authority_level, 'value') else str(src.authority_level)
                            authority_score = _AUTHORITY_WEIGHTS.get(al, 0.5)
        factors["authority_level"] = round(authority_score, 2)

        # Factor 2: Binding status
        is_binding = authority_score >= 0.7
        factors["is_binding"] = 1.0 if is_binding else 0.0

        # Factor 3: Obligation criticality
        ob_type = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
        crit_label = ob.criticality or _OBLIGATION_TYPE_CRITICALITY.get(ob_type, "medium")
        crit_score = _CRITICALITY_WEIGHTS.get(crit_label, 0.5)
        factors["obligation_criticality"] = round(crit_score, 2)

        # Factor 4: Missing controls
        ctrl_count = (await db.execute(
            select(func.count(ObligationControl.control_id)).where(
                ObligationControl.obligation_id == obligation_id
            )
        )).scalar() or 0
        missing_control_score = 1.0 if ctrl_count == 0 else max(0.0, 0.5 - ctrl_count * 0.15)
        factors["missing_controls"] = round(missing_control_score, 2)

        # Factor 5: Missing evidence
        if ctrl_count > 0:
            oc_result = await db.execute(
                select(ObligationControl.control_id).where(
                    ObligationControl.obligation_id == obligation_id
                )
            )
            ctrl_ids = [row[0] for row in oc_result.all()]
            controls_without_evidence = 0
            for cid in ctrl_ids:
                ev_count = (await db.execute(
                    select(func.count(EvidenceArtifact.id)).where(
                        EvidenceArtifact.control_id == cid,
                        EvidenceArtifact.status == "active",
                    )
                )).scalar() or 0
                if ev_count == 0:
                    controls_without_evidence += 1
            evidence_score = controls_without_evidence / len(ctrl_ids) if ctrl_ids else 0.0
        else:
            evidence_score = 1.0
        factors["missing_evidence"] = round(evidence_score, 2)

        # Factor 6: Review status / uncertainty
        rs = ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status)
        review_score = {"pending": 0.3, "needs_revision": 0.5, "rejected": 0.1, "approved": 0.0}.get(rs, 0.3)
        factors["review_uncertainty"] = round(review_score, 2)

        # Composite risk score: weighted average
        weights = {
            "authority_level": 0.20,
            "is_binding": 0.10,
            "obligation_criticality": 0.20,
            "missing_controls": 0.20,
            "missing_evidence": 0.15,
            "review_uncertainty": 0.15,
        }
        composite = sum(factors[k] * weights[k] for k in weights)
        composite = round(min(1.0, max(0.0, composite)), 3)

        # Map to severity / likelihood
        severity = "medium"
        likelihood = "possible"
        for lo, hi, sev, lik in _SEVERITY_MAP:
            if lo <= composite < hi:
                severity = sev
                likelihood = lik
                break

        return {
            "obligation_id": obligation_id,
            "obligation_type": ob_type,
            "regulator": regulator_abbr,
            "risk_score": composite,
            "severity": severity,
            "likelihood": likelihood,
            "factors": factors,
            "weights": weights,
            "explanation": RiskScoringService._explain(factors, composite, severity),
        }

    @staticmethod
    def _explain(factors: dict, composite: float, severity: str) -> str:
        parts = []
        if factors["missing_controls"] >= 0.8:
            parts.append("No controls are mapped to this obligation")
        if factors["missing_evidence"] >= 0.8:
            parts.append("Evidence is missing for linked controls")
        if factors["authority_level"] >= 0.8:
            parts.append("Source is a Tier 1 binding authority")
        if factors["obligation_criticality"] >= 0.75:
            parts.append("Obligation type is high-criticality")
        if factors["review_uncertainty"] >= 0.3:
            parts.append("Obligation has not been reviewed/approved")
        if not parts:
            parts.append("Risk factors are within acceptable thresholds")
        return f"Risk level: {severity} (score {composite:.2f}). " + "; ".join(parts) + "."

    @staticmethod
    async def score_all_obligations(db: AsyncSession) -> list[dict]:
        """Score all active obligations and persist RegulatoryRisk records."""
        result = await db.execute(
            select(Obligation).where(Obligation.is_active == True)
        )
        obligations = list(result.scalars().all())
        scores = []
        for ob in obligations:
            score = await RiskScoringService.score_obligation(db, ob.id)
            if score:
                scores.append(score)
                existing = await db.execute(
                    select(RegulatoryRisk).where(RegulatoryRisk.obligation_id == ob.id)
                )
                risk = existing.scalars().first()
                if risk:
                    risk.severity = score["severity"]
                    risk.likelihood = score["likelihood"]
                    risk.risk_score = score["risk_score"]
                    risk.risk_factors = score["factors"]
                    risk.description = score["explanation"]
                else:
                    risk = RegulatoryRisk(
                        id=generate_uuid(),
                        obligation_id=ob.id,
                        risk_type=RiskType.REGULATORY,
                        severity=score["severity"],
                        likelihood=score["likelihood"],
                        risk_score=score["risk_score"],
                        description=score["explanation"],
                        risk_factors=score["factors"],
                    )
                    db.add(risk)
        await db.flush()
        return scores

    @staticmethod
    async def get_risk_summary(db: AsyncSession) -> dict:
        result = await db.execute(select(RegulatoryRisk))
        risks = list(result.scalars().all())
        by_severity = defaultdict(int)
        by_type = defaultdict(int)
        scores = []
        for r in risks:
            by_severity[r.severity] += 1
            rt = r.risk_type.value if hasattr(r.risk_type, 'value') else str(r.risk_type)
            by_type[rt] += 1
            if r.risk_score is not None:
                scores.append(r.risk_score)
        return {
            "total_risks": len(risks),
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "avg_risk_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "high_risk_count": by_severity.get("high", 0) + by_severity.get("critical", 0),
        }


# ═══════════════════════════════════════════════════════════════════════
# 4. Gap Analysis Service
# ═══════════════════════════════════════════════════════════════════════

class GapAnalysisService:
    """Identify compliance gaps: unmapped obligations, missing evidence, high-risk items."""

    @staticmethod
    async def run_full_analysis(db: AsyncSession) -> dict:
        unmapped = await GapAnalysisService.obligations_without_controls(db)
        no_evidence = await GapAnalysisService.controls_without_evidence(db)
        high_risk = await GapAnalysisService.high_risk_obligations(db)
        needs_review = await GapAnalysisService.obligations_needing_review(db)

        total_obs = (await db.execute(
            select(func.count(Obligation.id)).where(Obligation.is_active == True)
        )).scalar() or 0
        total_ctrls = (await db.execute(select(func.count(Control.id)))).scalar() or 0
        total_ev = (await db.execute(select(func.count(EvidenceArtifact.id)))).scalar() or 0
        mapped_obs = (await db.execute(
            select(func.count(func.distinct(ObligationControl.obligation_id)))
        )).scalar() or 0

        return {
            "summary": {
                "total_obligations": total_obs,
                "mapped_obligations": mapped_obs,
                "unmapped_obligations": len(unmapped),
                "total_controls": total_ctrls,
                "controls_without_evidence": len(no_evidence),
                "total_evidence": total_ev,
                "high_risk_obligations": len(high_risk),
                "obligations_needing_review": len(needs_review),
                "control_coverage_pct": round(mapped_obs / total_obs * 100, 1) if total_obs else 0.0,
            },
            "gaps": {
                "unmapped_obligations": unmapped,
                "controls_without_evidence": no_evidence,
                "high_risk_obligations": high_risk,
                "obligations_needing_review": needs_review,
            },
        }

    @staticmethod
    async def obligations_without_controls(db: AsyncSession) -> list[dict]:
        mapped_sub = select(ObligationControl.obligation_id).distinct().subquery()
        result = await db.execute(
            select(Obligation).where(
                Obligation.is_active == True,
                ~Obligation.id.in_(select(mapped_sub.c.obligation_id))
            )
        )
        items = []
        for ob in result.scalars().all():
            prov = await db.get(Provision, ob.provision_id)
            regulator_abbr = None
            if prov:
                doc = await db.get(RegulatoryDocument, prov.document_id)
                if doc:
                    reg = await db.get(Regulator, doc.regulator_id)
                    regulator_abbr = reg.abbreviation if reg else None
            ot = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
            rs = ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status)
            items.append({
                "obligation_id": ob.id,
                "text": ob.text[:200],
                "obligation_type": ot,
                "regulator": regulator_abbr,
                "review_status": rs,
                "confidence": ob.confidence,
            })
        return items

    @staticmethod
    async def controls_without_evidence(db: AsyncSession) -> list[dict]:
        ev_sub = select(EvidenceArtifact.control_id).distinct().subquery()
        result = await db.execute(
            select(Control).where(~Control.id.in_(select(ev_sub.c.control_id)))
        )
        items = []
        for ctrl in result.scalars().all():
            ct = ctrl.control_type.value if hasattr(ctrl.control_type, 'value') else str(ctrl.control_type)
            st = ctrl.status.value if hasattr(ctrl.status, 'value') else str(ctrl.status)
            items.append({
                "control_id": ctrl.id,
                "name": ctrl.name,
                "control_type": ct,
                "owner": ctrl.owner,
                "status": st,
            })
        return items

    @staticmethod
    async def high_risk_obligations(db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(RegulatoryRisk).where(RegulatoryRisk.severity.in_(["high", "critical"]))
        )
        items = []
        for risk in result.scalars().all():
            ob = await db.get(Obligation, risk.obligation_id)
            if not ob:
                continue
            ot = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
            items.append({
                "obligation_id": ob.id,
                "text": ob.text[:200],
                "obligation_type": ot,
                "risk_score": risk.risk_score,
                "severity": risk.severity,
                "likelihood": risk.likelihood,
                "explanation": risk.description,
            })
        return items

    @staticmethod
    async def obligations_needing_review(db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(Obligation).where(
                Obligation.is_active == True,
                Obligation.review_status.in_([ReviewStatus.PENDING, ReviewStatus.NEEDS_REVISION])
            )
        )
        items = []
        for ob in result.scalars().all():
            ot = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
            rs = ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status)
            items.append({
                "obligation_id": ob.id,
                "text": ob.text[:200],
                "obligation_type": ot,
                "review_status": rs,
                "confidence": ob.confidence,
            })
        return items


# ═══════════════════════════════════════════════════════════════════════
# 5. Executive Reporting Service
# ═══════════════════════════════════════════════════════════════════════

class ExecutiveReportingService:
    """Board-ready compliance reporting."""

    @staticmethod
    async def generate_executive_report(db: AsyncSession) -> dict:
        total_obs = (await db.execute(
            select(func.count(Obligation.id)).where(Obligation.is_active == True)
        )).scalar() or 0

        mapped_count = (await db.execute(
            select(func.count(func.distinct(ObligationControl.obligation_id)))
        )).scalar() or 0
        unmapped_count = total_obs - mapped_count

        total_ctrls = (await db.execute(select(func.count(Control.id)))).scalar() or 0
        active_ctrls = (await db.execute(
            select(func.count(Control.id)).where(Control.status == ControlStatus.ACTIVE)
        )).scalar() or 0

        total_ev = (await db.execute(select(func.count(EvidenceArtifact.id)))).scalar() or 0
        active_ev = (await db.execute(
            select(func.count(EvidenceArtifact.id)).where(EvidenceArtifact.status == "active")
        )).scalar() or 0

        ctrls_with_ev = (await db.execute(
            select(func.count(func.distinct(EvidenceArtifact.control_id)))
        )).scalar() or 0
        ctrls_without_ev = total_ctrls - ctrls_with_ev

        risk_result = await db.execute(select(RegulatoryRisk))
        all_risks = list(risk_result.scalars().all())
        risk_by_severity = defaultdict(int)
        risk_scores = []
        for r in all_risks:
            risk_by_severity[r.severity] += 1
            if r.risk_score is not None:
                risk_scores.append(r.risk_score)

        by_regulator = await ExecutiveReportingService._breakdown_by_regulator(db)

        type_result = await db.execute(
            select(Obligation.obligation_type, func.count(Obligation.id)).where(
                Obligation.is_active == True
            ).group_by(Obligation.obligation_type)
        )
        by_type = {}
        for row in type_result.all():
            ot = row[0].value if hasattr(row[0], 'value') else str(row[0])
            by_type[ot] = row[1]

        review_result = await db.execute(
            select(Obligation.review_status, func.count(Obligation.id)).where(
                Obligation.is_active == True
            ).group_by(Obligation.review_status)
        )
        by_review = {}
        for row in review_result.all():
            rs = row[0].value if hasattr(row[0], 'value') else str(row[0])
            by_review[rs] = row[1]

        high_risk_gaps = []
        for r in all_risks:
            if r.severity in ("high", "critical"):
                ob = await db.get(Obligation, r.obligation_id)
                if ob:
                    high_risk_gaps.append({
                        "obligation_id": ob.id,
                        "text": ob.text[:150],
                        "severity": r.severity,
                        "risk_score": r.risk_score,
                        "explanation": r.description,
                    })

        return {
            "report_title": "AML Compliance OS \u2014 Executive Compliance Report",
            "report_title_ar": "\u0646\u0638\u0627\u0645 \u0627\u0644\u0627\u0645\u062a\u062b\u0627\u0644 \u0644\u0645\u0643\u0627\u0641\u062d\u0629 \u063a\u0633\u0644 \u0627\u0644\u0623\u0645\u0648\u0627\u0644 \u2014 \u062a\u0642\u0631\u064a\u0631 \u0627\u0644\u0627\u0645\u062a\u062b\u0627\u0644 \u0627\u0644\u062a\u0646\u0641\u064a\u0630\u064a",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overview": {
                "total_obligations": total_obs,
                "mapped_to_controls": mapped_count,
                "unmapped": unmapped_count,
                "control_coverage_pct": round(mapped_count / total_obs * 100, 1) if total_obs else 0.0,
                "total_controls": total_ctrls,
                "active_controls": active_ctrls,
                "total_evidence": total_ev,
                "active_evidence": active_ev,
                "evidence_coverage_pct": round(ctrls_with_ev / total_ctrls * 100, 1) if total_ctrls else 0.0,
                "controls_without_evidence": ctrls_without_ev,
            },
            "risk_summary": {
                "total_risks_assessed": len(all_risks),
                "by_severity": dict(risk_by_severity),
                "avg_risk_score": round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0.0,
                "high_risk_count": risk_by_severity.get("high", 0) + risk_by_severity.get("critical", 0),
            },
            "by_regulator": by_regulator,
            "by_obligation_type": by_type,
            "by_review_status": by_review,
            "high_risk_gaps": high_risk_gaps[:20],
            "recommendations": ExecutiveReportingService._generate_recommendations(
                total_obs, mapped_count, ctrls_without_ev, risk_by_severity, by_review,
            ),
        }

    @staticmethod
    async def _breakdown_by_regulator(db: AsyncSession) -> list[dict]:
        result = await db.execute(select(Obligation).where(Obligation.is_active == True))
        obligations = list(result.scalars().all())

        reg_data = defaultdict(lambda: {
            "total_obligations": 0, "mapped": 0, "unmapped": 0,
            "by_type": defaultdict(int), "by_review": defaultdict(int), "high_risk": 0,
        })

        for ob in obligations:
            prov = await db.get(Provision, ob.provision_id)
            reg_abbr = "Unknown"
            if prov:
                doc = await db.get(RegulatoryDocument, prov.document_id)
                if doc:
                    reg = await db.get(Regulator, doc.regulator_id)
                    if reg:
                        reg_abbr = reg.abbreviation

            reg_data[reg_abbr]["total_obligations"] += 1
            ot = ob.obligation_type.value if hasattr(ob.obligation_type, 'value') else str(ob.obligation_type)
            reg_data[reg_abbr]["by_type"][ot] += 1
            rs = ob.review_status.value if hasattr(ob.review_status, 'value') else str(ob.review_status)
            reg_data[reg_abbr]["by_review"][rs] += 1

            ctrl_count = (await db.execute(
                select(func.count(ObligationControl.control_id)).where(
                    ObligationControl.obligation_id == ob.id
                )
            )).scalar() or 0
            if ctrl_count > 0:
                reg_data[reg_abbr]["mapped"] += 1
            else:
                reg_data[reg_abbr]["unmapped"] += 1

        risk_result = await db.execute(
            select(RegulatoryRisk).where(RegulatoryRisk.severity.in_(["high", "critical"]))
        )
        for risk in risk_result.scalars().all():
            ob = await db.get(Obligation, risk.obligation_id)
            if ob:
                prov = await db.get(Provision, ob.provision_id)
                reg_abbr = "Unknown"
                if prov:
                    doc = await db.get(RegulatoryDocument, prov.document_id)
                    if doc:
                        reg = await db.get(Regulator, doc.regulator_id)
                        if reg:
                            reg_abbr = reg.abbreviation
                reg_data[reg_abbr]["high_risk"] += 1

        return [
            {
                "regulator": abbr,
                "total_obligations": d["total_obligations"],
                "mapped": d["mapped"],
                "unmapped": d["unmapped"],
                "coverage_pct": round(d["mapped"] / d["total_obligations"] * 100, 1) if d["total_obligations"] else 0.0,
                "by_type": dict(d["by_type"]),
                "by_review": dict(d["by_review"]),
                "high_risk": d["high_risk"],
            }
            for abbr, d in sorted(reg_data.items())
        ]

    @staticmethod
    def _generate_recommendations(
        total_obs: int, mapped: int, ctrls_without_ev: int,
        risk_by_severity: dict, by_review: dict,
    ) -> list[dict]:
        recs = []
        unmapped = total_obs - mapped
        coverage = mapped / total_obs * 100 if total_obs else 0

        if coverage < 50:
            recs.append({
                "priority": "critical", "area": "Control Coverage",
                "recommendation": f"Only {coverage:.0f}% of obligations have controls mapped. Prioritize mapping controls for high-criticality obligations.",
                "recommendation_ar": f"\u062a\u0645 \u0631\u0628\u0637 {coverage:.0f}% \u0641\u0642\u0637 \u0645\u0646 \u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a \u0628\u0636\u0648\u0627\u0628\u0637. \u064a\u062c\u0628 \u0625\u0639\u0637\u0627\u0621 \u0627\u0644\u0623\u0648\u0644\u0648\u064a\u0629 \u0644\u0631\u0628\u0637 \u0627\u0644\u0636\u0648\u0627\u0628\u0637 \u0628\u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a \u0639\u0627\u0644\u064a\u0629 \u0627\u0644\u0623\u0647\u0645\u064a\u0629.",
            })
        elif coverage < 80:
            recs.append({
                "priority": "high", "area": "Control Coverage",
                "recommendation": f"Control coverage is at {coverage:.0f}%. Target 80%+ by mapping remaining {unmapped} obligations.",
                "recommendation_ar": f"\u062a\u063a\u0637\u064a\u0629 \u0627\u0644\u0636\u0648\u0627\u0628\u0637 \u062d\u0627\u0644\u064a\u0627 {coverage:.0f}%. \u0627\u0633\u062a\u0647\u062f\u0641 \u062a\u063a\u0637\u064a\u0629 +80% \u0628\u0631\u0628\u0637 \u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a \u0627\u0644\u0645\u062a\u0628\u0642\u064a\u0629 ({unmapped}).",
            })

        if ctrls_without_ev > 0:
            recs.append({
                "priority": "high", "area": "Evidence Gaps",
                "recommendation": f"{ctrls_without_ev} control(s) have no supporting evidence. Collect and attach evidence artifacts.",
                "recommendation_ar": f"\u064a\u0648\u062c\u062f {ctrls_without_ev} \u0636\u0627\u0628\u0637/\u0636\u0648\u0627\u0628\u0637 \u0628\u062f\u0648\u0646 \u0623\u062f\u0644\u0629 \u062f\u0627\u0639\u0645\u0629. \u064a\u062c\u0628 \u062c\u0645\u0639 \u0648\u0625\u0631\u0641\u0627\u0642 \u0627\u0644\u0623\u062f\u0644\u0629.",
            })

        high_risk = risk_by_severity.get("high", 0) + risk_by_severity.get("critical", 0)
        if high_risk > 0:
            recs.append({
                "priority": "critical", "area": "Risk Mitigation",
                "recommendation": f"{high_risk} obligation(s) rated high/critical risk. Immediate remediation actions required.",
                "recommendation_ar": f"\u064a\u0648\u062c\u062f {high_risk} \u0627\u0644\u062a\u0632\u0627\u0645/\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a \u0645\u0635\u0646\u0641\u0629 \u0643\u0645\u062e\u0627\u0637\u0631 \u0639\u0627\u0644\u064a\u0629/\u062d\u0631\u062c\u0629. \u0645\u0637\u0644\u0648\u0628 \u0625\u062c\u0631\u0627\u0621\u0627\u062a \u0645\u0639\u0627\u0644\u062c\u0629 \u0641\u0648\u0631\u064a\u0629.",
            })

        pending = by_review.get("pending", 0) + by_review.get("needs_revision", 0)
        if pending > 0:
            recs.append({
                "priority": "medium", "area": "Review Backlog",
                "recommendation": f"{pending} obligation(s) awaiting review. Complete reviews to reduce uncertainty in risk scoring.",
                "recommendation_ar": f"\u064a\u0648\u062c\u062f {pending} \u0627\u0644\u062a\u0632\u0627\u0645/\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a \u0628\u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629. \u0623\u0643\u0645\u0644 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0627\u062a \u0644\u062a\u0642\u0644\u064a\u0644 \u0639\u062f\u0645 \u0627\u0644\u064a\u0642\u064a\u0646 \u0641\u064a \u062a\u0642\u064a\u064a\u0645 \u0627\u0644\u0645\u062e\u0627\u0637\u0631.",
            })

        if not recs:
            recs.append({
                "priority": "low", "area": "Compliance Posture",
                "recommendation": "Compliance posture is strong. Continue monitoring for regulatory changes.",
                "recommendation_ar": "\u0648\u0636\u0639 \u0627\u0644\u0627\u0645\u062a\u062b\u0627\u0644 \u0642\u0648\u064a. \u0627\u0633\u062a\u0645\u0631 \u0641\u064a \u0645\u0631\u0627\u0642\u0628\u0629 \u0627\u0644\u062a\u063a\u064a\u064a\u0631\u0627\u062a \u0627\u0644\u062a\u0646\u0638\u064a\u0645\u064a\u0629.",
            })

        return recs
