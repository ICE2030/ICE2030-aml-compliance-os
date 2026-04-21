"""Phase R: Regulatory Data Maturity Layer — Change Detection, Impact Propagation,
Alerting, Confidence & Freshness.

Services:
1. ChangeDetectionService — detect new/updated/removed documents and provisions
2. ImpactPropagationService — identify affected obligations/controls/evidence/risks
3. AlertingService — trigger alerts for high-impact changes
4. FreshnessService — track data freshness and confidence degradation
5. VersionComparisonService — compare provision versions with diff
"""
import hashlib
import difflib
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import generate_uuid
from app.models.regulatory.source import (
    Regulator, RegulatoryDocument, Provision, SourceVersion, Source, Jurisdiction,
)
from app.models.regulatory.obligation import (
    Obligation, Control, ObligationControl, EvidenceArtifact, RegulatoryRisk,
    RegulatoryAction,
)
from app.models.regulatory.phase_r import (
    ProvisionSnapshot,
    RegulatoryChange,
    ImpactRecord,
    RegulatoryAlert,
    RegulatorFreshness,
    ChangeClassification,
    ChangeScope,
    ImpactType,
    ImpactStatus,
    AlertSeverity,
    AlertStatus,
    FreshnessStatus,
)


def _hash_text(text: str) -> str:
    """SHA-256 hash of text for content comparison."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_provision_hash(prov: Provision) -> str:
    """Compute a content hash from a provision's text fields."""
    parts = [
        prov.section_number or "",
        prov.title or "",
        prov.title_ar or "",
        prov.text or "",
        prov.text_ar or "",
        str(prov.provision_type.value if hasattr(prov.provision_type, "value") else prov.provision_type),
    ]
    combined = "|||".join(parts)
    return _hash_text(combined)


def _classify_change(
    old_text: Optional[str],
    new_text: Optional[str],
    old_type: Optional[str],
    new_type: Optional[str],
) -> ChangeClassification:
    """Classify a provision change based on content diff analysis."""
    if old_text is None:
        # New provision
        if new_type and new_type in ("obligation", "prohibition", "penalty", "reporting"):
            return ChangeClassification.MATERIAL
        return ChangeClassification.OPERATIONAL

    if new_text is None:
        # Removed provision
        if old_type and old_type in ("obligation", "prohibition", "penalty", "reporting"):
            return ChangeClassification.MATERIAL
        return ChangeClassification.OPERATIONAL

    old_lower = (old_text or "").lower().strip()
    new_lower = (new_text or "").lower().strip()

    # Check if type changed (e.g., guidance -> obligation)
    if old_type != new_type:
        if new_type in ("obligation", "prohibition", "penalty"):
            return ChangeClassification.MATERIAL
        return ChangeClassification.OPERATIONAL

    # Calculate similarity
    ratio = difflib.SequenceMatcher(None, old_lower, new_lower).ratio()

    if ratio >= 0.98:
        return ChangeClassification.INFORMATIONAL  # trivial change
    if ratio >= 0.85:
        return ChangeClassification.INTERPRETIVE  # rewording
    if ratio >= 0.5:
        return ChangeClassification.OPERATIONAL  # significant change

    # Major rewrite
    return ChangeClassification.MATERIAL


def _generate_diff_html(old_text: str, new_text: str) -> str:
    """Generate an HTML diff between two texts."""
    old_lines = (old_text or "").splitlines(keepends=True)
    new_lines = (new_text or "").splitlines(keepends=True)

    diff = difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after", lineterm="")
    return "\n".join(diff)


def _generate_change_summary(
    scope: ChangeScope,
    old_text: Optional[str],
    new_text: Optional[str],
    section: Optional[str],
    classification: ChangeClassification,
) -> str:
    """Generate a human-readable change summary."""
    section_ref = f" (Section {section})" if section else ""

    if scope == ChangeScope.PROVISION_ADDED:
        snippet = (new_text or "")[:100]
        return f"New provision added{section_ref}: \"{snippet}...\""
    elif scope == ChangeScope.PROVISION_REMOVED:
        snippet = (old_text or "")[:100]
        return f"Provision removed{section_ref}: \"{snippet}...\""
    elif scope == ChangeScope.PROVISION_MODIFIED:
        if classification == ChangeClassification.INFORMATIONAL:
            return f"Minor formatting/text change{section_ref}"
        elif classification == ChangeClassification.INTERPRETIVE:
            return f"Provision rewording{section_ref} — interpretation may differ"
        elif classification == ChangeClassification.OPERATIONAL:
            return f"Significant provision update{section_ref} — operational impact likely"
        else:
            return f"Material provision change{section_ref} — review required immediately"
    elif scope == ChangeScope.DOCUMENT_NEW:
        return f"New regulatory document detected{section_ref}"
    elif scope == ChangeScope.DOCUMENT_UPDATED:
        return f"Document updated{section_ref}"
    elif scope == ChangeScope.OBLIGATION_ADDED:
        snippet = (new_text or "")[:100]
        return f"New obligation extracted{section_ref}: \"{snippet}...\""
    elif scope == ChangeScope.OBLIGATION_MODIFIED:
        return f"Obligation text changed{section_ref} — {classification.value} impact"
    elif scope == ChangeScope.OBLIGATION_REMOVED:
        return f"Obligation removed{section_ref} — may affect compliance posture"

    return f"Regulatory change detected{section_ref}"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Change Detection Service
# ═══════════════════════════════════════════════════════════════════════════════

class ChangeDetectionService:
    """Detects regulatory changes by comparing current data against snapshots."""

    @staticmethod
    async def create_baseline_snapshots(
        db: AsyncSession,
        regulator_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> dict:
        """Create initial snapshots for all provisions (baseline for future comparison).
        Does NOT overwrite existing snapshots."""
        now = datetime.now(timezone.utc)

        # Find provisions to snapshot
        query = select(Provision).join(
            RegulatoryDocument, Provision.document_id == RegulatoryDocument.id
        )
        if document_id:
            query = query.where(Provision.document_id == document_id)
        elif regulator_id:
            query = query.where(RegulatoryDocument.regulator_id == regulator_id)

        result = await db.execute(query)
        provisions = list(result.scalars().all())

        created = 0
        skipped = 0
        for prov in provisions:
            # Check if snapshot already exists for this provision
            existing = await db.execute(
                select(ProvisionSnapshot).where(
                    ProvisionSnapshot.provision_id == prov.id
                ).order_by(ProvisionSnapshot.version_number.desc()).limit(1)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            content_hash = _compute_provision_hash(prov)
            snapshot = ProvisionSnapshot(
                id=generate_uuid(),
                provision_id=prov.id,
                document_id=prov.document_id,
                version_number=1,
                section_number=prov.section_number,
                title=prov.title,
                title_ar=prov.title_ar,
                text=prov.text,
                text_ar=prov.text_ar,
                provision_type=str(prov.provision_type.value if hasattr(prov.provision_type, "value") else prov.provision_type),
                content_hash=content_hash,
                snapshot_at=now,
                snapshot_reason="initial_import",
            )
            db.add(snapshot)
            created += 1

        await db.flush()
        return {
            "total_provisions": len(provisions),
            "snapshots_created": created,
            "snapshots_skipped": skipped,
            "snapshot_at": now.isoformat(),
        }

    @staticmethod
    async def detect_changes(
        db: AsyncSession,
        regulator_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> dict:
        """Compare current provisions against latest snapshots to detect changes."""
        now = datetime.now(timezone.utc)

        # Get current provisions
        query = select(Provision).join(
            RegulatoryDocument, Provision.document_id == RegulatoryDocument.id
        )
        if document_id:
            query = query.where(Provision.document_id == document_id)
        elif regulator_id:
            query = query.where(RegulatoryDocument.regulator_id == regulator_id)

        result = await db.execute(query)
        current_provisions = list(result.scalars().all())

        # Build map of provision_id -> latest snapshot
        prov_ids = [p.id for p in current_provisions]
        snapshot_map = {}
        if prov_ids:
            for pid in prov_ids:
                snap_result = await db.execute(
                    select(ProvisionSnapshot).where(
                        ProvisionSnapshot.provision_id == pid
                    ).order_by(ProvisionSnapshot.version_number.desc()).limit(1)
                )
                snap = snap_result.scalar_one_or_none()
                if snap:
                    snapshot_map[pid] = snap

        changes = []
        new_provisions = 0
        modified_provisions = 0
        unchanged_provisions = 0

        for prov in current_provisions:
            current_hash = _compute_provision_hash(prov)
            latest_snapshot = snapshot_map.get(prov.id)

            if not latest_snapshot:
                # No snapshot exists — this is a new provision (no baseline yet)
                new_provisions += 1
                continue

            if current_hash == latest_snapshot.content_hash:
                unchanged_provisions += 1
                continue

            # Change detected!
            modified_provisions += 1

            old_type = latest_snapshot.provision_type
            new_type = str(prov.provision_type.value if hasattr(prov.provision_type, "value") else prov.provision_type)
            classification = _classify_change(
                latest_snapshot.text, prov.text, old_type, new_type
            )

            # Create new snapshot
            new_version = latest_snapshot.version_number + 1
            new_snapshot = ProvisionSnapshot(
                id=generate_uuid(),
                provision_id=prov.id,
                document_id=prov.document_id,
                version_number=new_version,
                section_number=prov.section_number,
                title=prov.title,
                title_ar=prov.title_ar,
                text=prov.text,
                text_ar=prov.text_ar,
                provision_type=new_type,
                content_hash=current_hash,
                snapshot_at=now,
                snapshot_reason="change_detected",
            )
            db.add(new_snapshot)
            await db.flush()

            # Determine regulator_id from document
            doc_result = await db.execute(
                select(RegulatoryDocument).where(RegulatoryDocument.id == prov.document_id)
            )
            doc = doc_result.scalar_one_or_none()
            reg_id = doc.regulator_id if doc else (regulator_id or "unknown")

            summary = _generate_change_summary(
                ChangeScope.PROVISION_MODIFIED,
                latest_snapshot.text, prov.text,
                prov.section_number, classification,
            )

            change = RegulatoryChange(
                id=generate_uuid(),
                document_id=prov.document_id,
                provision_id=prov.id,
                regulator_id=reg_id,
                change_scope=ChangeScope.PROVISION_MODIFIED,
                classification=classification,
                before_snapshot_id=latest_snapshot.id,
                after_snapshot_id=new_snapshot.id,
                summary=summary,
                affected_sections={"section_number": prov.section_number, "provision_id": prov.id},
                detected_at=now,
                detection_method="content_hash",
            )
            db.add(change)
            changes.append({
                "change_id": change.id,
                "provision_id": prov.id,
                "section": prov.section_number,
                "scope": change.change_scope.value,
                "classification": classification.value,
                "summary": summary,
                "before_version": latest_snapshot.version_number,
                "after_version": new_version,
            })

        await db.flush()

        return {
            "total_provisions": len(current_provisions),
            "new_provisions": new_provisions,
            "modified_provisions": modified_provisions,
            "unchanged_provisions": unchanged_provisions,
            "changes_detected": len(changes),
            "changes": changes,
            "detected_at": now.isoformat(),
        }

    @staticmethod
    async def detect_document_changes(
        db: AsyncSession,
        regulator_id: str,
    ) -> dict:
        """Detect new/removed documents for a regulator."""
        now = datetime.now(timezone.utc)

        # Get current documents
        result = await db.execute(
            select(RegulatoryDocument).where(
                RegulatoryDocument.regulator_id == regulator_id
            )
        )
        current_docs = list(result.scalars().all())

        # Get existing change records for this regulator's documents
        existing_doc_ids = set()
        for doc in current_docs:
            existing_doc_ids.add(doc.id)

        # Check for documents that have provisions without snapshots (new docs)
        new_docs = []
        for doc in current_docs:
            prov_result = await db.execute(
                select(func.count()).select_from(Provision).where(
                    Provision.document_id == doc.id
                )
            )
            prov_count = prov_result.scalar() or 0

            snap_result = await db.execute(
                select(func.count()).select_from(ProvisionSnapshot).where(
                    ProvisionSnapshot.document_id == doc.id
                )
            )
            snap_count = snap_result.scalar() or 0

            if prov_count > 0 and snap_count == 0:
                new_docs.append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "title_ar": doc.title_ar,
                    "provision_count": prov_count,
                })

        return {
            "regulator_id": regulator_id,
            "total_documents": len(current_docs),
            "new_documents": len(new_docs),
            "new_document_details": new_docs,
            "detected_at": now.isoformat(),
        }

    @staticmethod
    async def get_change_history(
        db: AsyncSession,
        regulator_id: Optional[str] = None,
        document_id: Optional[str] = None,
        classification: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Retrieve change history with filtering."""
        query = select(RegulatoryChange).order_by(RegulatoryChange.detected_at.desc())

        if regulator_id:
            query = query.where(RegulatoryChange.regulator_id == regulator_id)
        if document_id:
            query = query.where(RegulatoryChange.document_id == document_id)
        if classification:
            query = query.where(RegulatoryChange.classification == classification)

        # Count
        count_query = select(func.count()).select_from(RegulatoryChange)
        if regulator_id:
            count_query = count_query.where(RegulatoryChange.regulator_id == regulator_id)
        if document_id:
            count_query = count_query.where(RegulatoryChange.document_id == document_id)
        if classification:
            count_query = count_query.where(RegulatoryChange.classification == classification)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        result = await db.execute(query.offset(offset).limit(limit))
        changes = list(result.scalars().all())

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "changes": [
                {
                    "id": c.id,
                    "document_id": c.document_id,
                    "provision_id": c.provision_id,
                    "change_scope": c.change_scope.value if hasattr(c.change_scope, "value") else str(c.change_scope),
                    "classification": c.classification.value if hasattr(c.classification, "value") else str(c.classification),
                    "summary": c.summary,
                    "summary_ar": c.summary_ar,
                    "detected_at": c.detected_at.isoformat() if c.detected_at else None,
                    "review_status": c.review_status,
                    "before_snapshot_id": c.before_snapshot_id,
                    "after_snapshot_id": c.after_snapshot_id,
                }
                for c in changes
            ],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Impact Propagation Service
# ═══════════════════════════════════════════════════════════════════════════════

class ImpactPropagationService:
    """Propagate regulatory changes to downstream records (obligations, controls, etc.)."""

    @staticmethod
    async def propagate_change(db: AsyncSession, change_id: str) -> dict:
        """Given a regulatory change, identify all affected downstream records."""
        change_result = await db.execute(
            select(RegulatoryChange).where(RegulatoryChange.id == change_id)
        )
        change = change_result.scalar_one_or_none()
        if not change:
            return {"error": "Change not found"}

        impacts = []

        # 1. Find affected obligations (from the changed provision)
        if change.provision_id:
            obl_result = await db.execute(
                select(Obligation).where(Obligation.provision_id == change.provision_id)
            )
            obligations = list(obl_result.scalars().all())

            for obl in obligations:
                impact = ImpactRecord(
                    id=generate_uuid(),
                    change_id=change_id,
                    impact_type=ImpactType.OBLIGATION,
                    impacted_record_id=obl.id,
                    impacted_record_name=obl.text[:200] if obl.text else None,
                    impact_description=(
                        f"Obligation may be affected by {change.classification.value} "
                        f"change to provision: {change.summary}"
                    ),
                    suggested_action=_suggest_obligation_action(change.classification, obl),
                    status=ImpactStatus.REQUIRES_REVIEW,
                )
                db.add(impact)
                impacts.append({
                    "impact_id": impact.id,
                    "type": "obligation",
                    "record_id": obl.id,
                    "record_name": (obl.text or "")[:100],
                    "description": impact.impact_description,
                    "suggested_action": impact.suggested_action,
                })

                # 2. Find controls linked to affected obligations
                oc_result = await db.execute(
                    select(ObligationControl).where(
                        ObligationControl.obligation_id == obl.id
                    )
                )
                obligation_controls = list(oc_result.scalars().all())

                for oc in obligation_controls:
                    ctrl_result = await db.execute(
                        select(Control).where(Control.id == oc.control_id)
                    )
                    ctrl = ctrl_result.scalar_one_or_none()
                    if not ctrl:
                        continue

                    ctrl_impact = ImpactRecord(
                        id=generate_uuid(),
                        change_id=change_id,
                        impact_type=ImpactType.CONTROL,
                        impacted_record_id=ctrl.id,
                        impacted_record_name=ctrl.name,
                        impact_description=(
                            f"Control '{ctrl.name}' may need update — linked obligation "
                            f"affected by {change.classification.value} regulatory change"
                        ),
                        suggested_action=_suggest_control_action(change.classification, ctrl),
                        status=ImpactStatus.REQUIRES_REVIEW,
                    )
                    db.add(ctrl_impact)
                    impacts.append({
                        "impact_id": ctrl_impact.id,
                        "type": "control",
                        "record_id": ctrl.id,
                        "record_name": ctrl.name,
                        "description": ctrl_impact.impact_description,
                        "suggested_action": ctrl_impact.suggested_action,
                    })

                    # 3. Find evidence linked to affected controls
                    ev_result = await db.execute(
                        select(EvidenceArtifact).where(
                            EvidenceArtifact.control_id == ctrl.id
                        )
                    )
                    evidence_items = list(ev_result.scalars().all())

                    for ev in evidence_items:
                        ev_impact = ImpactRecord(
                            id=generate_uuid(),
                            change_id=change_id,
                            impact_type=ImpactType.EVIDENCE,
                            impacted_record_id=ev.id,
                            impacted_record_name=ev.name,
                            impact_description=(
                                f"Evidence '{ev.name}' may need refresh — parent control "
                                f"affected by regulatory change"
                            ),
                            suggested_action="Review evidence validity and refresh if needed",
                            status=ImpactStatus.REQUIRES_REVIEW,
                        )
                        db.add(ev_impact)
                        impacts.append({
                            "impact_id": ev_impact.id,
                            "type": "evidence",
                            "record_id": ev.id,
                            "record_name": ev.name,
                            "description": ev_impact.impact_description,
                            "suggested_action": ev_impact.suggested_action,
                        })

                # 4. Find risks linked to affected obligations
                risk_result = await db.execute(
                    select(RegulatoryRisk).where(
                        RegulatoryRisk.obligation_id == obl.id
                    )
                )
                risks = list(risk_result.scalars().all())

                for risk in risks:
                    risk_impact = ImpactRecord(
                        id=generate_uuid(),
                        change_id=change_id,
                        impact_type=ImpactType.RISK,
                        impacted_record_id=risk.id,
                        impacted_record_name=risk.description[:200] if risk.description else None,
                        impact_description=(
                            f"Risk assessment may be outdated — linked obligation "
                            f"affected by {change.classification.value} change"
                        ),
                        suggested_action="Re-score risk based on updated obligation",
                        status=ImpactStatus.REQUIRES_REVIEW,
                    )
                    db.add(risk_impact)
                    impacts.append({
                        "impact_id": risk_impact.id,
                        "type": "risk",
                        "record_id": risk.id,
                        "record_name": (risk.description or "")[:100],
                        "description": risk_impact.impact_description,
                        "suggested_action": risk_impact.suggested_action,
                    })

                # 5. Find actions linked to affected obligations
                action_result = await db.execute(
                    select(RegulatoryAction).where(
                        RegulatoryAction.obligation_id == obl.id
                    )
                )
                actions = list(action_result.scalars().all())

                for action in actions:
                    action_impact = ImpactRecord(
                        id=generate_uuid(),
                        change_id=change_id,
                        impact_type=ImpactType.ACTION,
                        impacted_record_id=action.id,
                        impacted_record_name=action.description[:200] if action.description else None,
                        impact_description=(
                            f"Action may need update — linked obligation affected by "
                            f"regulatory change"
                        ),
                        suggested_action="Review action relevance and update if needed",
                        status=ImpactStatus.REQUIRES_REVIEW,
                    )
                    db.add(action_impact)
                    impacts.append({
                        "impact_id": action_impact.id,
                        "type": "action",
                        "record_id": action.id,
                        "record_name": (action.description or "")[:100],
                        "description": action_impact.impact_description,
                        "suggested_action": action_impact.suggested_action,
                    })

        await db.flush()

        # Summary by type
        by_type = {}
        for imp in impacts:
            t = imp["type"]
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "change_id": change_id,
            "classification": change.classification.value if hasattr(change.classification, "value") else str(change.classification),
            "total_impacts": len(impacts),
            "impacts_by_type": by_type,
            "impacts": impacts,
        }

    @staticmethod
    async def propagate_all_pending(db: AsyncSession) -> dict:
        """Find all changes without impact records and propagate them."""
        # Find changes that have no impact records yet
        result = await db.execute(
            select(RegulatoryChange).where(
                RegulatoryChange.review_status == "pending"
            )
        )
        pending_changes = list(result.scalars().all())

        total_impacts = 0
        propagated_changes = 0

        for change in pending_changes:
            # Check if impacts already exist for this change
            existing = await db.execute(
                select(func.count()).select_from(ImpactRecord).where(
                    ImpactRecord.change_id == change.id
                )
            )
            if (existing.scalar() or 0) > 0:
                continue

            result = await ImpactPropagationService.propagate_change(db, change.id)
            if "error" not in result:
                total_impacts += result.get("total_impacts", 0)
                propagated_changes += 1

        return {
            "pending_changes_found": len(pending_changes),
            "changes_propagated": propagated_changes,
            "total_impacts_created": total_impacts,
        }

    @staticmethod
    async def get_impacts(
        db: AsyncSession,
        change_id: Optional[str] = None,
        impact_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get impact records with filtering."""
        query = select(ImpactRecord).order_by(ImpactRecord.created_at.desc())

        if change_id:
            query = query.where(ImpactRecord.change_id == change_id)
        if impact_type:
            query = query.where(ImpactRecord.impact_type == impact_type)
        if status:
            query = query.where(ImpactRecord.status == status)

        count_query = select(func.count()).select_from(ImpactRecord)
        if change_id:
            count_query = count_query.where(ImpactRecord.change_id == change_id)
        if impact_type:
            count_query = count_query.where(ImpactRecord.impact_type == impact_type)
        if status:
            count_query = count_query.where(ImpactRecord.status == status)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        result = await db.execute(query.offset(offset).limit(limit))
        records = list(result.scalars().all())

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "impacts": [
                {
                    "id": r.id,
                    "change_id": r.change_id,
                    "impact_type": r.impact_type.value if hasattr(r.impact_type, "value") else str(r.impact_type),
                    "impacted_record_id": r.impacted_record_id,
                    "impacted_record_name": r.impacted_record_name,
                    "impact_description": r.impact_description,
                    "suggested_action": r.suggested_action,
                    "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                    "resolved_by": r.resolved_by,
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ],
        }

    @staticmethod
    async def resolve_impact(
        db: AsyncSession,
        impact_id: str,
        status: str,
        resolved_by: str = "system",
        notes: Optional[str] = None,
    ) -> dict:
        """Resolve an impact record."""
        result = await db.execute(
            select(ImpactRecord).where(ImpactRecord.id == impact_id)
        )
        impact = result.scalar_one_or_none()
        if not impact:
            return {"error": "Impact not found"}

        impact.status = ImpactStatus(status) if status in [e.value for e in ImpactStatus] else ImpactStatus.REVIEWED
        impact.resolved_by = resolved_by
        impact.resolved_at = datetime.now(timezone.utc)
        impact.resolution_notes = notes

        await db.flush()
        return {
            "impact_id": impact_id,
            "new_status": impact.status.value,
            "resolved_by": resolved_by,
        }


def _suggest_obligation_action(classification: ChangeClassification, obl: Obligation) -> str:
    """Suggest action for an affected obligation based on change classification."""
    if classification == ChangeClassification.MATERIAL:
        return (
            "URGENT: Re-extract obligation from updated provision. "
            "Review binding status, penalties, and deadlines. "
            "Update risk score and control mappings."
        )
    elif classification == ChangeClassification.OPERATIONAL:
        return (
            "Review obligation text for operational changes. "
            "Check if deadlines, reporting requirements, or procedures changed."
        )
    elif classification == ChangeClassification.INTERPRETIVE:
        return (
            "Review rewording for interpretive changes. "
            "Confirm obligation intent has not changed."
        )
    return "Minor change — review at next scheduled review cycle."


def _suggest_control_action(classification: ChangeClassification, ctrl: Control) -> str:
    """Suggest action for an affected control."""
    if classification == ChangeClassification.MATERIAL:
        return (
            f"URGENT: Review control '{ctrl.name}' for adequacy. "
            "Underlying obligation has materially changed. "
            "May need new controls or control updates."
        )
    elif classification == ChangeClassification.OPERATIONAL:
        return (
            f"Review control '{ctrl.name}' — operational change in linked obligation. "
            "Check if control procedures need adjustment."
        )
    return f"Monitor control '{ctrl.name}' — minor upstream change."


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Alerting Service
# ═══════════════════════════════════════════════════════════════════════════════

class AlertingService:
    """Generate and manage regulatory alerts based on changes and impacts."""

    @staticmethod
    async def generate_alerts_for_change(db: AsyncSession, change_id: str) -> list:
        """Generate alerts based on a regulatory change and its impacts."""
        change_result = await db.execute(
            select(RegulatoryChange).where(RegulatoryChange.id == change_id)
        )
        change = change_result.scalar_one_or_none()
        if not change:
            return []

        alerts = []
        classification = change.classification
        scope = change.change_scope

        # Count impacts
        impact_result = await db.execute(
            select(ImpactRecord).where(ImpactRecord.change_id == change_id)
        )
        impacts = list(impact_result.scalars().all())

        obl_count = sum(1 for i in impacts if i.impact_type == ImpactType.OBLIGATION)
        ctrl_count = sum(1 for i in impacts if i.impact_type == ImpactType.CONTROL)
        ev_count = sum(1 for i in impacts if i.impact_type == ImpactType.EVIDENCE)

        # Rule: Material change → CRITICAL alert
        if classification == ChangeClassification.MATERIAL:
            alert = RegulatoryAlert(
                id=generate_uuid(),
                change_id=change_id,
                regulator_id=change.regulator_id,
                title=f"Material Regulatory Change Detected",
                title_ar="تم اكتشاف تغيير تنظيمي جوهري",
                description=change.summary,
                description_ar=change.summary_ar or change.summary,
                severity=AlertSeverity.CRITICAL,
                alert_type="material_change",
                affected_obligations_count=obl_count,
                affected_controls_count=ctrl_count,
                affected_evidence_count=ev_count,
            )
            db.add(alert)
            alerts.append(_alert_to_dict(alert))

        # Rule: New binding obligation → HIGH alert
        if scope in (ChangeScope.OBLIGATION_ADDED, ChangeScope.PROVISION_ADDED):
            # Check if the provision contains obligations
            if change.provision_id:
                obl_check = await db.execute(
                    select(func.count()).select_from(Obligation).where(
                        Obligation.provision_id == change.provision_id
                    )
                )
                if (obl_check.scalar() or 0) > 0:
                    alert = RegulatoryAlert(
                        id=generate_uuid(),
                        change_id=change_id,
                        regulator_id=change.regulator_id,
                        title="New Binding Obligation Added",
                        title_ar="تمت إضافة التزام ملزم جديد",
                        description=f"New provision with obligations detected: {change.summary}",
                        description_ar=change.summary_ar,
                        severity=AlertSeverity.HIGH,
                        alert_type="new_binding_obligation",
                        affected_obligations_count=obl_count,
                        affected_controls_count=ctrl_count,
                        affected_evidence_count=ev_count,
                    )
                    db.add(alert)
                    alerts.append(_alert_to_dict(alert))

        # Rule: Operational change with many impacts → HIGH alert
        if classification == ChangeClassification.OPERATIONAL and len(impacts) >= 3:
            alert = RegulatoryAlert(
                id=generate_uuid(),
                change_id=change_id,
                regulator_id=change.regulator_id,
                title="High-Impact Operational Change",
                title_ar="تغيير تشغيلي عالي التأثير",
                description=f"Operational change affecting {len(impacts)} records: {change.summary}",
                description_ar=change.summary_ar,
                severity=AlertSeverity.HIGH,
                alert_type="high_impact_change",
                affected_obligations_count=obl_count,
                affected_controls_count=ctrl_count,
                affected_evidence_count=ev_count,
            )
            db.add(alert)
            alerts.append(_alert_to_dict(alert))

        # Rule: Obligation removed → MEDIUM alert
        if scope == ChangeScope.OBLIGATION_REMOVED:
            alert = RegulatoryAlert(
                id=generate_uuid(),
                change_id=change_id,
                regulator_id=change.regulator_id,
                title="Obligation Removed",
                title_ar="تمت إزالة الالتزام",
                description=f"An obligation was removed: {change.summary}",
                description_ar=change.summary_ar,
                severity=AlertSeverity.MEDIUM,
                alert_type="obligation_removed",
                affected_obligations_count=obl_count,
                affected_controls_count=ctrl_count,
                affected_evidence_count=ev_count,
            )
            db.add(alert)
            alerts.append(_alert_to_dict(alert))

        await db.flush()
        return alerts

    @staticmethod
    async def get_alerts(
        db: AsyncSession,
        regulator_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get alerts with filtering."""
        query = select(RegulatoryAlert).order_by(RegulatoryAlert.created_at.desc())

        if regulator_id:
            query = query.where(RegulatoryAlert.regulator_id == regulator_id)
        if severity:
            query = query.where(RegulatoryAlert.severity == severity)
        if status:
            query = query.where(RegulatoryAlert.status == status)

        count_query = select(func.count()).select_from(RegulatoryAlert)
        if regulator_id:
            count_query = count_query.where(RegulatoryAlert.regulator_id == regulator_id)
        if severity:
            count_query = count_query.where(RegulatoryAlert.severity == severity)
        if status:
            count_query = count_query.where(RegulatoryAlert.status == status)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        result = await db.execute(query.offset(offset).limit(limit))
        alerts = list(result.scalars().all())

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "alerts": [_alert_to_dict(a) for a in alerts],
        }

    @staticmethod
    async def acknowledge_alert(
        db: AsyncSession,
        alert_id: str,
        acknowledged_by: str = "system",
    ) -> dict:
        """Acknowledge an alert."""
        result = await db.execute(
            select(RegulatoryAlert).where(RegulatoryAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return {"error": "Alert not found"}

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now(timezone.utc)
        await db.flush()

        return {"alert_id": alert_id, "status": "acknowledged"}

    @staticmethod
    async def resolve_alert(
        db: AsyncSession,
        alert_id: str,
    ) -> dict:
        """Resolve an alert."""
        result = await db.execute(
            select(RegulatoryAlert).where(RegulatoryAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return {"error": "Alert not found"}

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        await db.flush()

        return {"alert_id": alert_id, "status": "resolved"}

    @staticmethod
    async def dismiss_alert(
        db: AsyncSession,
        alert_id: str,
    ) -> dict:
        """Dismiss an alert."""
        result = await db.execute(
            select(RegulatoryAlert).where(RegulatoryAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return {"error": "Alert not found"}

        alert.status = AlertStatus.DISMISSED
        await db.flush()

        return {"alert_id": alert_id, "status": "dismissed"}


def _alert_to_dict(alert: RegulatoryAlert) -> dict:
    """Convert alert to dict."""
    return {
        "id": alert.id,
        "change_id": alert.change_id,
        "regulator_id": alert.regulator_id,
        "title": alert.title,
        "title_ar": alert.title_ar,
        "description": alert.description,
        "description_ar": alert.description_ar,
        "severity": alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
        "alert_type": alert.alert_type,
        "affected_obligations_count": alert.affected_obligations_count,
        "affected_controls_count": alert.affected_controls_count,
        "affected_evidence_count": alert.affected_evidence_count,
        "status": alert.status.value if hasattr(alert.status, "value") else str(alert.status),
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Freshness Service
# ═══════════════════════════════════════════════════════════════════════════════

class FreshnessService:
    """Track and compute data freshness and confidence per regulator."""

    @staticmethod
    async def compute_freshness(db: AsyncSession, regulator_id: str) -> dict:
        """Compute and store freshness/confidence for a regulator."""
        now = datetime.now(timezone.utc)

        # Get or create freshness record
        result = await db.execute(
            select(RegulatorFreshness).where(
                RegulatorFreshness.regulator_id == regulator_id
            )
        )
        freshness = result.scalar_one_or_none()

        if not freshness:
            freshness = RegulatorFreshness(
                id=generate_uuid(),
                regulator_id=regulator_id,
            )
            db.add(freshness)

        # Count documents, provisions, obligations
        doc_count = (await db.execute(
            select(func.count()).select_from(RegulatoryDocument).where(
                RegulatoryDocument.regulator_id == regulator_id
            )
        )).scalar() or 0

        prov_count = (await db.execute(
            select(func.count()).select_from(Provision).join(
                RegulatoryDocument, Provision.document_id == RegulatoryDocument.id
            ).where(RegulatoryDocument.regulator_id == regulator_id)
        )).scalar() or 0

        obl_count = (await db.execute(
            select(func.count()).select_from(Obligation).join(
                Provision, Obligation.provision_id == Provision.id
            ).join(
                RegulatoryDocument, Provision.document_id == RegulatoryDocument.id
            ).where(RegulatoryDocument.regulator_id == regulator_id)
        )).scalar() or 0

        # Count pending reviews (impacts)
        pending_count = (await db.execute(
            select(func.count()).select_from(ImpactRecord).join(
                RegulatoryChange, ImpactRecord.change_id == RegulatoryChange.id
            ).where(
                RegulatoryChange.regulator_id == regulator_id,
                ImpactRecord.status == ImpactStatus.REQUIRES_REVIEW,
            )
        )).scalar() or 0

        # Count total changes
        change_count = (await db.execute(
            select(func.count()).select_from(RegulatoryChange).where(
                RegulatoryChange.regulator_id == regulator_id
            )
        )).scalar() or 0

        # Last change detected
        last_change_result = await db.execute(
            select(RegulatoryChange.detected_at).where(
                RegulatoryChange.regulator_id == regulator_id
            ).order_by(RegulatoryChange.detected_at.desc()).limit(1)
        )
        last_change_row = last_change_result.first()
        last_change_at = last_change_row[0] if last_change_row else None

        # Last snapshot (indicates last data update)
        last_snap_result = await db.execute(
            select(ProvisionSnapshot.snapshot_at).join(
                RegulatoryDocument, ProvisionSnapshot.document_id == RegulatoryDocument.id
            ).where(
                RegulatoryDocument.regulator_id == regulator_id
            ).order_by(ProvisionSnapshot.snapshot_at.desc()).limit(1)
        )
        last_snap_row = last_snap_result.first()
        last_update_at = last_snap_row[0] if last_snap_row else freshness.created_at

        # Compute days since last update
        if last_update_at:
            if last_update_at.tzinfo is None:
                last_update_at = last_update_at.replace(tzinfo=timezone.utc)
            days_since = (now - last_update_at).days
        else:
            days_since = None

        # Compute freshness status
        expected_freq = freshness.expected_update_frequency_days
        if days_since is None:
            status = FreshnessStatus.UNKNOWN
        elif days_since <= expected_freq:
            status = FreshnessStatus.CURRENT
        elif days_since <= expected_freq * 2:
            status = FreshnessStatus.AGING
        else:
            status = FreshnessStatus.STALE

        # Compute confidence score (degrades past expected window)
        if days_since is not None and days_since > expected_freq:
            overdue_days = days_since - expected_freq
            degradation = overdue_days * freshness.confidence_degradation_rate
            confidence = max(0.0, 1.0 - degradation)
        else:
            confidence = 1.0

        # Update record
        freshness.last_checked_at = now
        freshness.last_updated_at = last_update_at
        freshness.last_change_detected_at = last_change_at
        freshness.freshness_status = status
        freshness.days_since_last_update = days_since
        freshness.confidence_score = round(confidence, 3)
        freshness.total_documents = doc_count
        freshness.total_provisions = prov_count
        freshness.total_obligations = obl_count
        freshness.total_changes_detected = change_count
        freshness.total_pending_reviews = pending_count

        await db.flush()

        return {
            "regulator_id": regulator_id,
            "freshness_status": status.value,
            "confidence_score": freshness.confidence_score,
            "days_since_last_update": days_since,
            "expected_update_frequency_days": expected_freq,
            "last_checked_at": now.isoformat(),
            "last_updated_at": last_update_at.isoformat() if last_update_at else None,
            "last_change_detected_at": last_change_at.isoformat() if last_change_at else None,
            "total_documents": doc_count,
            "total_provisions": prov_count,
            "total_obligations": obl_count,
            "total_changes_detected": change_count,
            "total_pending_reviews": pending_count,
        }

    @staticmethod
    async def compute_all_freshness(db: AsyncSession) -> dict:
        """Compute freshness for all regulators."""
        result = await db.execute(select(Regulator))
        regulators = list(result.scalars().all())

        results = []
        for reg in regulators:
            f = await FreshnessService.compute_freshness(db, reg.id)
            results.append(f)

        return {
            "regulators_checked": len(results),
            "results": results,
        }

    @staticmethod
    async def get_freshness_dashboard(db: AsyncSession) -> dict:
        """Get freshness dashboard for all regulators."""
        result = await db.execute(
            select(RegulatorFreshness).order_by(RegulatorFreshness.confidence_score.asc())
        )
        records = list(result.scalars().all())

        # Enrich with regulator names
        dashboard = []
        for r in records:
            reg_result = await db.execute(
                select(Regulator).where(Regulator.id == r.regulator_id)
            )
            reg = reg_result.scalar_one_or_none()

            dashboard.append({
                "regulator_id": r.regulator_id,
                "regulator_name": reg.name if reg else "Unknown",
                "regulator_name_ar": reg.name_ar if reg else None,
                "abbreviation": reg.abbreviation if reg else None,
                "freshness_status": r.freshness_status.value if hasattr(r.freshness_status, "value") else str(r.freshness_status),
                "confidence_score": r.confidence_score,
                "days_since_last_update": r.days_since_last_update,
                "total_documents": r.total_documents,
                "total_provisions": r.total_provisions,
                "total_obligations": r.total_obligations,
                "total_changes_detected": r.total_changes_detected,
                "total_pending_reviews": r.total_pending_reviews,
                "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None,
                "last_updated_at": r.last_updated_at.isoformat() if r.last_updated_at else None,
            })

        return {
            "total_regulators": len(dashboard),
            "regulators": dashboard,
        }

    @staticmethod
    async def generate_freshness_alert(
        db: AsyncSession,
        regulator_id: str,
    ) -> Optional[dict]:
        """Generate a freshness degradation alert if regulator data is stale."""
        result = await db.execute(
            select(RegulatorFreshness).where(
                RegulatorFreshness.regulator_id == regulator_id
            )
        )
        freshness = result.scalar_one_or_none()
        if not freshness:
            return None

        if freshness.freshness_status in (FreshnessStatus.STALE, FreshnessStatus.AGING):
            # Check if we already have a recent freshness alert
            existing = await db.execute(
                select(RegulatoryAlert).where(
                    RegulatoryAlert.regulator_id == regulator_id,
                    RegulatoryAlert.alert_type == "freshness_degraded",
                    RegulatoryAlert.status == AlertStatus.ACTIVE,
                )
            )
            if existing.scalar_one_or_none():
                return None  # Already have an active freshness alert

            reg_result = await db.execute(
                select(Regulator).where(Regulator.id == regulator_id)
            )
            reg = reg_result.scalar_one_or_none()
            reg_name = reg.name if reg else "Unknown"

            severity = AlertSeverity.HIGH if freshness.freshness_status == FreshnessStatus.STALE else AlertSeverity.MEDIUM

            alert = RegulatoryAlert(
                id=generate_uuid(),
                regulator_id=regulator_id,
                title=f"Regulatory Data Freshness Degraded — {reg_name}",
                title_ar=f"تدهور حداثة البيانات التنظيمية — {reg.name_ar if reg else reg_name}",
                description=(
                    f"{reg_name} data has not been updated in "
                    f"{freshness.days_since_last_update} days "
                    f"(expected every {freshness.expected_update_frequency_days} days). "
                    f"Confidence score: {freshness.confidence_score}"
                ),
                severity=severity,
                alert_type="freshness_degraded",
                affected_obligations_count=freshness.total_obligations,
                affected_controls_count=0,
                affected_evidence_count=0,
            )
            db.add(alert)
            await db.flush()

            return _alert_to_dict(alert)

        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Version Comparison Service
# ═══════════════════════════════════════════════════════════════════════════════

class VersionComparisonService:
    """Compare versions of provisions and documents."""

    @staticmethod
    async def compare_provision_versions(
        db: AsyncSession,
        provision_id: str,
    ) -> dict:
        """Get all versions of a provision with diffs between each."""
        result = await db.execute(
            select(ProvisionSnapshot).where(
                ProvisionSnapshot.provision_id == provision_id
            ).order_by(ProvisionSnapshot.version_number.asc())
        )
        snapshots = list(result.scalars().all())

        if not snapshots:
            return {"provision_id": provision_id, "versions": [], "total_versions": 0}

        versions = []
        for i, snap in enumerate(snapshots):
            version_data = {
                "snapshot_id": snap.id,
                "version_number": snap.version_number,
                "section_number": snap.section_number,
                "title": snap.title,
                "title_ar": snap.title_ar,
                "text": snap.text,
                "text_ar": snap.text_ar,
                "provision_type": snap.provision_type,
                "content_hash": snap.content_hash,
                "snapshot_at": snap.snapshot_at.isoformat() if snap.snapshot_at else None,
                "snapshot_reason": snap.snapshot_reason,
            }

            # Diff against previous version
            if i > 0:
                prev = snapshots[i - 1]
                diff_en = _generate_diff_html(prev.text or "", snap.text or "")
                diff_ar = _generate_diff_html(prev.text_ar or "", snap.text_ar or "") if (prev.text_ar or snap.text_ar) else None

                version_data["diff_from_previous"] = {
                    "diff_en": diff_en,
                    "diff_ar": diff_ar,
                    "previous_version": prev.version_number,
                    "text_changed": prev.text != snap.text,
                    "text_ar_changed": prev.text_ar != snap.text_ar,
                    "title_changed": prev.title != snap.title,
                    "type_changed": prev.provision_type != snap.provision_type,
                }
            else:
                version_data["diff_from_previous"] = None

            versions.append(version_data)

        return {
            "provision_id": provision_id,
            "total_versions": len(versions),
            "versions": versions,
        }

    @staticmethod
    async def compare_document_versions(
        db: AsyncSession,
        document_id: str,
    ) -> dict:
        """Compare all provision changes within a document."""
        # Get all snapshots for this document grouped by provision
        result = await db.execute(
            select(ProvisionSnapshot).where(
                ProvisionSnapshot.document_id == document_id
            ).order_by(
                ProvisionSnapshot.provision_id,
                ProvisionSnapshot.version_number.asc(),
            )
        )
        snapshots = list(result.scalars().all())

        # Group by provision_id
        provision_versions = {}
        for snap in snapshots:
            if snap.provision_id not in provision_versions:
                provision_versions[snap.provision_id] = []
            provision_versions[snap.provision_id].append(snap)

        # Get document info
        doc_result = await db.execute(
            select(RegulatoryDocument).where(RegulatoryDocument.id == document_id)
        )
        doc = doc_result.scalar_one_or_none()

        changed_provisions = []
        unchanged_provisions = []
        for prov_id, versions in provision_versions.items():
            if len(versions) > 1:
                latest = versions[-1]
                previous = versions[-2]
                classification = _classify_change(
                    previous.text, latest.text,
                    previous.provision_type, latest.provision_type,
                )
                changed_provisions.append({
                    "provision_id": prov_id,
                    "section_number": latest.section_number,
                    "title": latest.title,
                    "versions_count": len(versions),
                    "latest_version": latest.version_number,
                    "classification": classification.value,
                    "diff_en": _generate_diff_html(previous.text or "", latest.text or ""),
                })
            else:
                unchanged_provisions.append({
                    "provision_id": prov_id,
                    "section_number": versions[0].section_number,
                    "title": versions[0].title,
                })

        return {
            "document_id": document_id,
            "document_title": doc.title if doc else None,
            "document_title_ar": doc.title_ar if doc else None,
            "total_provisions": len(provision_versions),
            "changed_provisions": len(changed_provisions),
            "unchanged_provisions": len(unchanged_provisions),
            "changes": changed_provisions,
            "unchanged": unchanged_provisions,
        }

    @staticmethod
    async def get_provision_at_version(
        db: AsyncSession,
        provision_id: str,
        version_number: int,
    ) -> Optional[dict]:
        """Get a specific version of a provision."""
        result = await db.execute(
            select(ProvisionSnapshot).where(
                ProvisionSnapshot.provision_id == provision_id,
                ProvisionSnapshot.version_number == version_number,
            )
        )
        snap = result.scalar_one_or_none()
        if not snap:
            return None

        return {
            "snapshot_id": snap.id,
            "provision_id": snap.provision_id,
            "version_number": snap.version_number,
            "section_number": snap.section_number,
            "title": snap.title,
            "title_ar": snap.title_ar,
            "text": snap.text,
            "text_ar": snap.text_ar,
            "provision_type": snap.provision_type,
            "content_hash": snap.content_hash,
            "snapshot_at": snap.snapshot_at.isoformat() if snap.snapshot_at else None,
            "snapshot_reason": snap.snapshot_reason,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Orchestrator — Run Full Phase R Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class PhaseROrchestrator:
    """Orchestrate the full Phase R pipeline: detect → propagate → alert → freshness."""

    @staticmethod
    async def run_full_pipeline(
        db: AsyncSession,
        regulator_id: Optional[str] = None,
    ) -> dict:
        """Run the complete Phase R pipeline for a regulator or all regulators."""

        # 1. Create baseline snapshots if needed
        baseline = await ChangeDetectionService.create_baseline_snapshots(
            db, regulator_id=regulator_id
        )

        # 2. Detect changes
        changes = await ChangeDetectionService.detect_changes(
            db, regulator_id=regulator_id
        )

        # 3. Propagate impacts for each change
        propagation_results = []
        for change_data in changes.get("changes", []):
            impact_result = await ImpactPropagationService.propagate_change(
                db, change_data["change_id"]
            )
            propagation_results.append(impact_result)

            # 4. Generate alerts
            alerts = await AlertingService.generate_alerts_for_change(
                db, change_data["change_id"]
            )

        # 5. Compute freshness
        if regulator_id:
            freshness = await FreshnessService.compute_freshness(db, regulator_id)
            # Check for freshness alerts
            await FreshnessService.generate_freshness_alert(db, regulator_id)
            freshness_results = [freshness]
        else:
            freshness_data = await FreshnessService.compute_all_freshness(db)
            freshness_results = freshness_data.get("results", [])
            # Check freshness alerts for all
            for f in freshness_results:
                await FreshnessService.generate_freshness_alert(db, f["regulator_id"])

        total_impacts = sum(r.get("total_impacts", 0) for r in propagation_results)

        # Count alerts
        alert_result = await db.execute(
            select(func.count()).select_from(RegulatoryAlert).where(
                RegulatoryAlert.status == AlertStatus.ACTIVE
            )
        )
        active_alerts = alert_result.scalar() or 0

        return {
            "baseline": baseline,
            "changes": {
                "total_provisions_checked": changes.get("total_provisions", 0),
                "changes_detected": changes.get("changes_detected", 0),
                "new_provisions": changes.get("new_provisions", 0),
                "modified_provisions": changes.get("modified_provisions", 0),
                "unchanged_provisions": changes.get("unchanged_provisions", 0),
            },
            "impacts": {
                "changes_propagated": len(propagation_results),
                "total_impacts": total_impacts,
            },
            "alerts": {
                "active_alerts": active_alerts,
            },
            "freshness": freshness_results,
        }
