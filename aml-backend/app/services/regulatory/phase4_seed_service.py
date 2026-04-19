"""Phase 4 Seed Service: Create sample controls, evidence, and mappings.

Demonstrates the full chain: Source -> Provision -> Obligation -> Control -> Evidence -> Risk -> Action
Seeds are idempotent via seed_key fields.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.obligation import (
    Obligation, Control, ObligationControl, EvidenceArtifact,
    ControlType, ControlStatus,
)
from app.models.regulatory.source import Regulator
from app.models.base import generate_uuid
from app.services.regulatory.phase4_service import RiskScoringService

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Sample Controls (mapped to FATF, Saudi AML, SAMA obligations)
# ═══════════════════════════════════════════════════════════════════════

SAMPLE_CONTROLS = [
    {
        "seed_key": "ctrl-cdd-policy",
        "name": "Customer Due Diligence Policy",
        "name_ar": "سياسة العناية الواجبة بالعملاء",
        "description": "Comprehensive CDD policy requiring identity verification, risk assessment, and ongoing monitoring for all customers.",
        "description_ar": "سياسة شاملة للعناية الواجبة تتطلب التحقق من الهوية وتقييم المخاطر والمراقبة المستمرة لجميع العملاء.",
        "control_type": "policy",
        "owner": "Compliance Department",
        "frequency": "continuous",
        "status": "active",
        "obligation_keywords": ["due diligence", "identity", "customer identification", "CDD", "التحقق من هوية"],
    },
    {
        "seed_key": "ctrl-str-procedure",
        "name": "Suspicious Transaction Reporting Procedure",
        "name_ar": "إجراءات الإبلاغ عن المعاملات المشبوهة",
        "description": "Standard operating procedure for detecting, escalating, and reporting suspicious transactions to SAFIU.",
        "description_ar": "إجراءات تشغيلية موحدة للكشف عن المعاملات المشبوهة وتصعيدها والإبلاغ عنها إلى وحدة التحريات المالية.",
        "control_type": "procedure",
        "owner": "AML Unit",
        "frequency": "continuous",
        "status": "active",
        "obligation_keywords": ["suspicious", "report", "الإبلاغ", "مشبوهة", "SAFIU"],
    },
    {
        "seed_key": "ctrl-sanctions-screening",
        "name": "Automated Sanctions Screening System",
        "name_ar": "نظام الفحص الآلي للعقوبات",
        "description": "Real-time screening of customers and transactions against UN, OFAC, and local sanctions lists.",
        "description_ar": "فحص آلي في الوقت الفعلي للعملاء والمعاملات مقابل قوائم العقوبات الأممية والمحلية.",
        "control_type": "technical",
        "owner": "IT Security",
        "frequency": "continuous",
        "status": "active",
        "obligation_keywords": ["sanction", "freeze", "تجميد", "عقوبات", "designated"],
    },
    {
        "seed_key": "ctrl-transaction-monitoring",
        "name": "Transaction Monitoring System",
        "name_ar": "نظام مراقبة المعاملات",
        "description": "Automated system monitoring transactions for unusual patterns, threshold breaches, and AML red flags.",
        "description_ar": "نظام آلي لمراقبة المعاملات بحثاً عن أنماط غير عادية وتجاوزات حدود ومؤشرات غسل الأموال.",
        "control_type": "monitoring",
        "owner": "AML Unit",
        "frequency": "continuous",
        "status": "active",
        "obligation_keywords": ["monitor", "threshold", "transaction", "مراقبة", "معامل"],
    },
    {
        "seed_key": "ctrl-aml-training",
        "name": "AML/CTF Staff Training Program",
        "name_ar": "برنامج تدريب الموظفين على مكافحة غسل الأموال",
        "description": "Annual training program covering AML/CTF regulations, red flags, reporting obligations, and sanctions compliance.",
        "description_ar": "برنامج تدريبي سنوي يغطي أنظمة مكافحة غسل الأموال وتمويل الإرهاب والمؤشرات والإبلاغ والعقوبات.",
        "control_type": "training",
        "owner": "HR / Compliance",
        "frequency": "annual",
        "status": "active",
        "obligation_keywords": ["training", "تدريب", "awareness", "program"],
    },
    {
        "seed_key": "ctrl-recordkeeping",
        "name": "Record Retention Policy",
        "name_ar": "سياسة الاحتفاظ بالسجلات",
        "description": "Policy requiring retention of customer records, transaction data, and STR documentation for minimum 10 years.",
        "description_ar": "سياسة تتطلب الاحتفاظ بسجلات العملاء وبيانات المعاملات ووثائق الإبلاغ لمدة 10 سنوات على الأقل.",
        "control_type": "policy",
        "owner": "Compliance Department",
        "frequency": "continuous",
        "status": "active",
        "obligation_keywords": ["record", "retain", "سجل", "احتفاظ", "maintain"],
    },
    {
        "seed_key": "ctrl-bo-verification",
        "name": "Beneficial Ownership Verification Process",
        "name_ar": "عملية التحقق من المستفيد الحقيقي",
        "description": "Process for identifying and verifying beneficial owners of legal entities and arrangements.",
        "description_ar": "عملية لتحديد والتحقق من المستفيدين الحقيقيين للكيانات والترتيبات القانونية.",
        "control_type": "procedure",
        "owner": "Compliance Department",
        "frequency": "per-transaction",
        "status": "active",
        "obligation_keywords": ["beneficial owner", "المستفيد الحقيقي", "ownership", "legal person"],
    },
    {
        "seed_key": "ctrl-pep-screening",
        "name": "PEP Screening and Enhanced Due Diligence",
        "name_ar": "فحص الأشخاص المعرضين سياسياً والعناية المعززة",
        "description": "Screening for politically exposed persons with enhanced due diligence and senior management approval.",
        "description_ar": "فحص الأشخاص المعرضين سياسياً مع عناية واجبة معززة وموافقة الإدارة العليا.",
        "control_type": "procedure",
        "owner": "AML Unit",
        "frequency": "per-transaction",
        "status": "active",
        "obligation_keywords": ["PEP", "politically exposed", "enhanced", "معرض سياسي"],
    },
]

# ═══════════════════════════════════════════════════════════════════════
# Sample Evidence Artifacts
# ═══════════════════════════════════════════════════════════════════════

SAMPLE_EVIDENCE = {
    "ctrl-cdd-policy": [
        {
            "seed_key": "ev-cdd-policy-doc",
            "name": "CDD Policy Document v3.2",
            "name_ar": "وثيقة سياسة العناية الواجبة الإصدار 3.2",
            "artifact_type": "policy_doc",
            "description": "Board-approved CDD policy document, last updated Q1 2026.",
            "source_system": "Document Management System",
            "collection_method": "manual",
            "periodicity": "annual",
            "owner": "Chief Compliance Officer",
        },
        {
            "seed_key": "ev-cdd-completion-report",
            "name": "CDD Completion Rate Report",
            "name_ar": "تقرير معدل إكمال العناية الواجبة",
            "artifact_type": "report",
            "description": "Monthly report showing CDD completion rates across all customer segments.",
            "source_system": "Core Banking System",
            "collection_method": "automated",
            "periodicity": "monthly",
            "owner": "Operations",
        },
    ],
    "ctrl-str-procedure": [
        {
            "seed_key": "ev-str-sop-doc",
            "name": "STR Filing Standard Operating Procedure",
            "name_ar": "إجراءات التشغيل الموحدة للإبلاغ عن المعاملات المشبوهة",
            "artifact_type": "policy_doc",
            "description": "Step-by-step SOP for identifying, escalating, and filing STRs with SAFIU.",
            "source_system": "Document Management System",
            "collection_method": "manual",
            "periodicity": "annual",
            "owner": "AML Unit Head",
        },
        {
            "seed_key": "ev-str-filing-log",
            "name": "STR Filing Log",
            "name_ar": "سجل الإبلاغ عن المعاملات المشبوهة",
            "artifact_type": "log",
            "description": "System log of all STRs filed, including timestamps, case IDs, and filing confirmations.",
            "source_system": "AML Case Management",
            "collection_method": "system_generated",
            "periodicity": "continuous",
            "owner": "AML Unit",
        },
    ],
    "ctrl-sanctions-screening": [
        {
            "seed_key": "ev-sanctions-config",
            "name": "Sanctions List Configuration Certificate",
            "name_ar": "شهادة تكوين قوائم العقوبات",
            "artifact_type": "certificate",
            "description": "Configuration certificate showing all active sanctions lists (UN, OFAC, local) and update frequency.",
            "source_system": "Screening System",
            "collection_method": "automated",
            "periodicity": "quarterly",
            "owner": "IT Security",
        },
    ],
    "ctrl-transaction-monitoring": [
        {
            "seed_key": "ev-tm-alert-report",
            "name": "Transaction Monitoring Alert Summary",
            "name_ar": "ملخص تنبيهات مراقبة المعاملات",
            "artifact_type": "report",
            "description": "Monthly summary of TM alerts generated, investigated, and cleared.",
            "source_system": "Transaction Monitoring System",
            "collection_method": "automated",
            "periodicity": "monthly",
            "owner": "AML Unit",
        },
    ],
    "ctrl-aml-training": [
        {
            "seed_key": "ev-training-records",
            "name": "AML Training Completion Records",
            "name_ar": "سجلات إكمال التدريب على مكافحة غسل الأموال",
            "artifact_type": "training_record",
            "description": "Records of staff AML/CTF training completion with scores and dates.",
            "source_system": "Learning Management System",
            "collection_method": "automated",
            "periodicity": "annual",
            "owner": "HR Department",
        },
    ],
    "ctrl-recordkeeping": [
        {
            "seed_key": "ev-retention-attestation",
            "name": "Record Retention Compliance Attestation",
            "name_ar": "شهادة الامتثال للاحتفاظ بالسجلات",
            "artifact_type": "attestation",
            "description": "Annual attestation confirming all records meet 10-year retention requirement.",
            "source_system": "Compliance System",
            "collection_method": "manual",
            "periodicity": "annual",
            "owner": "Chief Compliance Officer",
        },
    ],
    "ctrl-bo-verification": [
        {
            "seed_key": "ev-bo-register",
            "name": "Beneficial Ownership Register Extract",
            "name_ar": "مستخرج سجل المستفيدين الحقيقيين",
            "artifact_type": "system_output",
            "description": "System extract of beneficial ownership records for all legal entity customers.",
            "source_system": "Core Banking / KYC System",
            "collection_method": "semi_automated",
            "periodicity": "quarterly",
            "owner": "Compliance Department",
        },
    ],
    "ctrl-pep-screening": [
        {
            "seed_key": "ev-pep-screening-log",
            "name": "PEP Screening Results Log",
            "name_ar": "سجل نتائج فحص الأشخاص المعرضين سياسياً",
            "artifact_type": "log",
            "description": "Automated log of all PEP screening results with match dispositions.",
            "source_system": "Screening System",
            "collection_method": "system_generated",
            "periodicity": "continuous",
            "owner": "AML Unit",
        },
    ],
}


class Phase4SeedService:
    """Seed Phase 4 controls, evidence, and mappings. Idempotent via seed_key."""

    @staticmethod
    async def seed_all(db: AsyncSession) -> dict:
        stats = {"controls_created": 0, "evidence_created": 0, "mappings_created": 0, "risks_scored": 0}

        # Get regulators for linking
        reg_result = await db.execute(select(Regulator))
        regulators = {r.abbreviation: r.id for r in reg_result.scalars().all()}

        # 1. Create controls
        control_map = {}  # seed_key -> control_id
        for ctrl_def in SAMPLE_CONTROLS:
            existing = await db.execute(
                select(Control).where(Control.seed_key == ctrl_def["seed_key"])
            )
            ctrl = existing.scalar_one_or_none()
            if ctrl:
                control_map[ctrl_def["seed_key"]] = ctrl.id
                continue

            # Pick a regulator if we can match
            reg_id = None
            for abbr in ["SAMA", "FATF", "Saudi AML"]:
                if abbr in regulators:
                    reg_id = regulators[abbr]
                    break

            ctrl = Control(
                id=generate_uuid(),
                name=ctrl_def["name"],
                name_ar=ctrl_def["name_ar"],
                description=ctrl_def["description"],
                description_ar=ctrl_def.get("description_ar"),
                control_type=ControlType(ctrl_def["control_type"]),
                owner=ctrl_def["owner"],
                frequency=ctrl_def["frequency"],
                status=ControlStatus(ctrl_def["status"]),
                regulator_id=reg_id,
                seed_key=ctrl_def["seed_key"],
            )
            db.add(ctrl)
            await db.flush()
            control_map[ctrl_def["seed_key"]] = ctrl.id
            stats["controls_created"] += 1

        # 2. Create evidence artifacts
        for ctrl_seed_key, evidence_list in SAMPLE_EVIDENCE.items():
            ctrl_id = control_map.get(ctrl_seed_key)
            if not ctrl_id:
                continue
            for ev_def in evidence_list:
                existing = await db.execute(
                    select(EvidenceArtifact).where(EvidenceArtifact.seed_key == ev_def["seed_key"])
                )
                if existing.scalar_one_or_none():
                    continue
                ev = EvidenceArtifact(
                    id=generate_uuid(),
                    control_id=ctrl_id,
                    name=ev_def["name"],
                    name_ar=ev_def.get("name_ar"),
                    artifact_type=ev_def["artifact_type"],
                    description=ev_def.get("description"),
                    source_system=ev_def.get("source_system"),
                    collection_method=ev_def.get("collection_method"),
                    periodicity=ev_def.get("periodicity"),
                    owner=ev_def.get("owner"),
                    status="active",
                    seed_key=ev_def["seed_key"],
                    collected_at=datetime.now(timezone.utc),
                )
                db.add(ev)
                stats["evidence_created"] += 1

        await db.flush()

        # 3. Auto-map obligations to controls by keyword matching
        obligations_result = await db.execute(
            select(Obligation).where(Obligation.is_active == True)
        )
        obligations = list(obligations_result.scalars().all())

        for ctrl_def in SAMPLE_CONTROLS:
            ctrl_id = control_map.get(ctrl_def["seed_key"])
            if not ctrl_id:
                continue
            keywords = ctrl_def.get("obligation_keywords", [])
            for ob in obligations:
                text_lower = (ob.text or "").lower()
                matched = any(kw.lower() in text_lower for kw in keywords)
                if not matched:
                    continue
                # Check if mapping exists
                existing = await db.execute(
                    select(ObligationControl).where(
                        ObligationControl.obligation_id == ob.id,
                        ObligationControl.control_id == ctrl_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                mapping = ObligationControl(
                    obligation_id=ob.id,
                    control_id=ctrl_id,
                    mapping_confidence=0.85,
                    mapping_method="keyword_match",
                    notes=f"Auto-mapped via seed keywords: {', '.join(keywords[:3])}",
                )
                db.add(mapping)
                stats["mappings_created"] += 1

        await db.flush()

        # 4. Score all obligations
        scores = await RiskScoringService.score_all_obligations(db)
        stats["risks_scored"] = len(scores)

        await db.flush()
        logger.info(f"Phase 4 seed complete: {stats}")
        return stats
