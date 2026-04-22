"""Cross-linking service — Phase G3.

Provides provenance chain traversal across:
risk → audit findings → issues → remediation → actions
obligation → control → evidence → risk → action

Returns linked entities with clear navigation paths.
"""
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.grc.enterprise_risk import EnterpriseRisk
from app.models.grc.issue import Issue, RemediationAction
from app.models.grc.audit import AuditFinding, AuditEngagement, ControlTest
from app.models.grc.action import GRCAction, ActionSourceType, ActionStatus
from app.models.regulatory.obligation import Obligation, Control, EvidenceArtifact, ObligationControl

logger = logging.getLogger(__name__)


class CrossLinkService:
    """Traverse and display entity cross-links."""

    @staticmethod
    async def get_entity_links(db: AsyncSession, entity_type: str, entity_id: str) -> dict:
        """Get all linked entities for a given entity."""
        links = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_title": None,
            "risks": [],
            "issues": [],
            "findings": [],
            "obligations": [],
            "controls": [],
            "evidence": [],
            "actions": [],
            "remediation": [],
        }

        if entity_type == "risk":
            await _link_from_risk(db, entity_id, links)
        elif entity_type == "issue":
            await _link_from_issue(db, entity_id, links)
        elif entity_type == "audit_finding":
            await _link_from_finding(db, entity_id, links)
        elif entity_type == "obligation":
            await _link_from_obligation(db, entity_id, links)
        elif entity_type == "control":
            await _link_from_control(db, entity_id, links)
        elif entity_type == "evidence":
            await _link_from_evidence(db, entity_id, links)
        elif entity_type == "action":
            await _link_from_action(db, entity_id, links)

        return links


async def _link_from_risk(db: AsyncSession, risk_id: str, links: dict):
    """Get links starting from a risk entity."""
    result = await db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))
    risk = result.scalars().first()
    if not risk:
        return
    links["entity_title"] = risk.title

    # Risk → Issues (via risk_id FK field)
    issues = await db.execute(select(Issue).where(Issue.risk_id == risk_id))
    for issue in issues.scalars().all():
        links["issues"].append({"id": issue.id, "title": issue.title, "status": issue.status.value})

    # Risk → Findings (via risk_ids JSON field)
    findings = await db.execute(select(AuditFinding))
    for finding in findings.scalars().all():
        if finding.risk_ids and risk_id in (finding.risk_ids if isinstance(finding.risk_ids, list) else []):
            links["findings"].append({"id": finding.id, "title": finding.title, "severity": finding.severity.value, "status": finding.status.value})

    # Risk → Actions
    actions = await db.execute(
        select(GRCAction).where(
            GRCAction.source_type == ActionSourceType.RISK,
            GRCAction.source_id == risk_id,
        )
    )
    for action in actions.scalars().all():
        links["actions"].append({"id": action.id, "title": action.title, "priority": action.priority.value, "status": action.status.value})

    # Also check linked_risk_ids
    linked_actions = await db.execute(select(GRCAction))
    for action in linked_actions.scalars().all():
        if action.linked_risk_ids and risk_id in (action.linked_risk_ids if isinstance(action.linked_risk_ids, list) else []):
            if not any(a["id"] == action.id for a in links["actions"]):
                links["actions"].append({"id": action.id, "title": action.title, "priority": action.priority.value, "status": action.status.value})

    # Risk → Obligation (via obligation_id FK on risk)
    if risk.obligation_id:
        obl_result = await db.execute(select(Obligation).where(Obligation.id == risk.obligation_id))
        obl = obl_result.scalars().first()
        if obl:
            links["obligations"].append({"id": obl.id, "title": obl.normalized_summary or obl.text[:80]})


async def _link_from_issue(db: AsyncSession, issue_id: str, links: dict):
    """Get links starting from an issue."""
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalars().first()
    if not issue:
        return
    links["entity_title"] = issue.title

    # Issue → Remediation actions
    remediations = await db.execute(
        select(RemediationAction).where(RemediationAction.issue_id == issue_id)
    )
    for rem in remediations.scalars().all():
        links["remediation"].append({"id": rem.id, "title": rem.title, "status": rem.status.value})

    # Issue → Risk (via risk_id FK)
    if issue.risk_id:
        risk_result = await db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == issue.risk_id))
        risk = risk_result.scalars().first()
        if risk:
            links["risks"].append({"id": risk.id, "title": risk.title, "residual_score": risk.residual_score})

    # Issue → Actions
    actions = await db.execute(
        select(GRCAction).where(
            GRCAction.source_type == ActionSourceType.ISSUE,
            GRCAction.source_id == issue_id,
        )
    )
    for action in actions.scalars().all():
        links["actions"].append({"id": action.id, "title": action.title, "priority": action.priority.value, "status": action.status.value})


async def _link_from_finding(db: AsyncSession, finding_id: str, links: dict):
    """Get links starting from an audit finding."""
    result = await db.execute(select(AuditFinding).where(AuditFinding.id == finding_id))
    finding = result.scalars().first()
    if not finding:
        return
    links["entity_title"] = finding.title

    # Finding → Risks
    if finding.risk_ids:
        for rid in (finding.risk_ids if isinstance(finding.risk_ids, list) else []):
            risk_result = await db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == rid))
            risk = risk_result.scalars().first()
            if risk:
                links["risks"].append({"id": risk.id, "title": risk.title})

    # Finding → Controls
    if finding.control_ids:
        for cid in (finding.control_ids if isinstance(finding.control_ids, list) else []):
            ctrl_result = await db.execute(select(Control).where(Control.id == cid))
            ctrl = ctrl_result.scalars().first()
            if ctrl:
                links["controls"].append({"id": ctrl.id, "title": ctrl.name})

    # Finding → Obligations
    if finding.obligation_ids:
        for oid in (finding.obligation_ids if isinstance(finding.obligation_ids, list) else []):
            obl_result = await db.execute(select(Obligation).where(Obligation.id == oid))
            obl = obl_result.scalars().first()
            if obl:
                links["obligations"].append({"id": obl.id, "title": obl.normalized_summary or obl.text[:80]})

    # Finding → Actions
    actions = await db.execute(
        select(GRCAction).where(
            GRCAction.source_type == ActionSourceType.AUDIT_FINDING,
            GRCAction.source_id == finding_id,
        )
    )
    for action in actions.scalars().all():
        links["actions"].append({"id": action.id, "title": action.title, "priority": action.priority.value, "status": action.status.value})


async def _link_from_obligation(db: AsyncSession, obligation_id: str, links: dict):
    """Get links starting from an obligation."""
    result = await db.execute(select(Obligation).where(Obligation.id == obligation_id))
    obl = result.scalars().first()
    if not obl:
        return
    links["entity_title"] = obl.normalized_summary or (obl.text[:80] if obl.text else obligation_id)

    # Obligation → Controls (via ObligationControl junction)
    oc_results = await db.execute(
        select(ObligationControl).where(ObligationControl.obligation_id == obligation_id)
    )
    for oc in oc_results.scalars().all():
        ctrl_result = await db.execute(select(Control).where(Control.id == oc.control_id))
        ctrl = ctrl_result.scalars().first()
        if ctrl:
            links["controls"].append({"id": ctrl.id, "title": ctrl.name})

    # Obligation → Evidence (via controls)
    for ctrl_link in links["controls"]:
        evidence = await db.execute(select(EvidenceArtifact).where(EvidenceArtifact.control_id == ctrl_link["id"]))
        for ev in evidence.scalars().all():
            links["evidence"].append({"id": ev.id, "title": ev.name})

    # Obligation → Actions
    actions = await db.execute(
        select(GRCAction).where(
            GRCAction.source_type == ActionSourceType.OBLIGATION,
            GRCAction.source_id == obligation_id,
        )
    )
    for action in actions.scalars().all():
        links["actions"].append({"id": action.id, "title": action.title, "priority": action.priority.value, "status": action.status.value})


async def _link_from_control(db: AsyncSession, control_id: str, links: dict):
    """Get links starting from a control."""
    result = await db.execute(select(Control).where(Control.id == control_id))
    ctrl = result.scalars().first()
    if not ctrl:
        return
    links["entity_title"] = ctrl.name

    # Control → Obligations (via ObligationControl junction)
    oc_results = await db.execute(
        select(ObligationControl).where(ObligationControl.control_id == control_id)
    )
    for oc in oc_results.scalars().all():
        obl_result = await db.execute(select(Obligation).where(Obligation.id == oc.obligation_id))
        obl = obl_result.scalars().first()
        if obl:
            links["obligations"].append({"id": obl.id, "title": obl.normalized_summary or obl.text[:80]})

    # Control → Evidence
    evidence = await db.execute(select(EvidenceArtifact).where(EvidenceArtifact.control_id == control_id))
    for ev in evidence.scalars().all():
        links["evidence"].append({"id": ev.id, "title": ev.name})

    # Control → Actions
    actions = await db.execute(
        select(GRCAction).where(
            GRCAction.source_type == ActionSourceType.CONTROL,
            GRCAction.source_id == control_id,
        )
    )
    for action in actions.scalars().all():
        links["actions"].append({"id": action.id, "title": action.title, "priority": action.priority.value, "status": action.status.value})


async def _link_from_evidence(db: AsyncSession, evidence_id: str, links: dict):
    """Get links starting from evidence."""
    result = await db.execute(select(EvidenceArtifact).where(EvidenceArtifact.id == evidence_id))
    ev = result.scalars().first()
    if not ev:
        return
    links["entity_title"] = ev.name

    # Evidence → Control
    if ev.control_id:
        ctrl_result = await db.execute(select(Control).where(Control.id == ev.control_id))
        ctrl = ctrl_result.scalars().first()
        if ctrl:
            links["controls"].append({"id": ctrl.id, "title": ctrl.name})

    # Evidence → Actions
    actions = await db.execute(
        select(GRCAction).where(
            GRCAction.source_type == ActionSourceType.EVIDENCE,
            GRCAction.source_id == evidence_id,
        )
    )
    for action in actions.scalars().all():
        links["actions"].append({"id": action.id, "title": action.title, "priority": action.priority.value, "status": action.status.value})


async def _link_from_action(db: AsyncSession, action_id: str, links: dict):
    """Get links starting from an action."""
    result = await db.execute(select(GRCAction).where(GRCAction.id == action_id))
    action = result.scalars().first()
    if not action:
        return
    links["entity_title"] = action.title

    # Action → Source entity
    if action.source_id:
        if action.source_type == ActionSourceType.RISK:
            r = await db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == action.source_id))
            risk = r.scalars().first()
            if risk:
                links["risks"].append({"id": risk.id, "title": risk.title})
        elif action.source_type == ActionSourceType.ISSUE:
            r = await db.execute(select(Issue).where(Issue.id == action.source_id))
            issue = r.scalars().first()
            if issue:
                links["issues"].append({"id": issue.id, "title": issue.title})
        elif action.source_type == ActionSourceType.AUDIT_FINDING:
            r = await db.execute(select(AuditFinding).where(AuditFinding.id == action.source_id))
            finding = r.scalars().first()
            if finding:
                links["findings"].append({"id": finding.id, "title": finding.title})
        elif action.source_type == ActionSourceType.OBLIGATION:
            r = await db.execute(select(Obligation).where(Obligation.id == action.source_id))
            obl = r.scalars().first()
            if obl:
                links["obligations"].append({"id": obl.id, "title": obl.normalized_summary or obl.text[:80]})
        elif action.source_type == ActionSourceType.CONTROL:
            r = await db.execute(select(Control).where(Control.id == action.source_id))
            ctrl = r.scalars().first()
            if ctrl:
                links["controls"].append({"id": ctrl.id, "title": ctrl.name})
        elif action.source_type == ActionSourceType.EVIDENCE:
            r = await db.execute(select(EvidenceArtifact).where(EvidenceArtifact.id == action.source_id))
            ev = r.scalars().first()
            if ev:
                links["evidence"].append({"id": ev.id, "title": ev.name})

    # Action → Linked entities
    if action.linked_risk_ids:
        for rid in (action.linked_risk_ids if isinstance(action.linked_risk_ids, list) else []):
            r = await db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == rid))
            risk = r.scalars().first()
            if risk and not any(x["id"] == risk.id for x in links["risks"]):
                links["risks"].append({"id": risk.id, "title": risk.title})

    if action.linked_issue_ids:
        for iid in (action.linked_issue_ids if isinstance(action.linked_issue_ids, list) else []):
            r = await db.execute(select(Issue).where(Issue.id == iid))
            issue = r.scalars().first()
            if issue and not any(x["id"] == issue.id for x in links["issues"]):
                links["issues"].append({"id": issue.id, "title": issue.title})
