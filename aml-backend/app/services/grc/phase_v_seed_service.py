"""Phase V — Sample realistic GRC data for Saudi regulated environment.

Seeds a small, carefully-curated set of enterprise risks, issues, audit plans /
engagements / findings / responses, remediation actions, and unified GRC
actions. Each record is aligned with SAMA, CMA, or Insurance Authority (IA)
expectations and linked to existing regulators where possible.

Idempotent: the seed_key for each record is stored under tags["seed_key"]
(GRC tables don't have a dedicated seed_key column). Re-running the seed
inserts only missing rows.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import generate_uuid
from app.models.grc.action import (
    ActionOrigin,
    ActionPriority,
    ActionSourceType,
    ActionStatus,
    GRCAction,
)
from app.models.grc.audit import (
    AuditEngagement,
    AuditFinding,
    AuditPlan,
    AuditPlanStatus,
    EngagementStatus,
    FindingSeverity,
    FindingStatus,
    ManagementResponse,
    ResponseStatus,
)
from app.models.grc.enterprise_risk import (
    EnterpriseRisk,
    ImpactLevel,
    LikelihoodLevel,
    RiskCategoryEnum,
    RiskStatus,
    TreatmentStrategy,
    TrendDirection,
)
from app.models.grc.issue import (
    EscalationStatus,
    Issue,
    IssueSeverity,
    IssueSource,
    IssueStatus,
    RemediationAction,
    RemediationStatus,
)
from app.models.regulatory.source import Regulator
from app.services.grc.enterprise_risk_service import compute_risk_score

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days(n: int) -> datetime:
    return _now() + timedelta(days=n)


# ══════════════════════════════════════════════════════════════════════════
#  Enterprise Risks — anchored in SAMA / CMA / IA context
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_RISKS: list[dict] = [
    {
        "seed_key": "phv-risk-sama-aml-ctf",
        "regulator_abbr": "SAMA",
        "title": "Inadequate AML/CTF Controls Against SAMA Requirements",
        "title_ar": "ضعف ضوابط مكافحة غسل الأموال وتمويل الإرهاب مقارنة بمتطلبات البنك المركزي",
        "description": (
            "Risk that customer due diligence, transaction monitoring, or "
            "suspicious transaction reporting falls short of SAMA AML/CTF "
            "Rules, leading to regulatory sanction and loss of license privileges."
        ),
        "description_ar": (
            "خطر عدم كفاية العناية الواجبة بالعملاء ومراقبة المعاملات والإبلاغ "
            "عن العمليات المشبوهة مقارنة بقواعد مكافحة غسل الأموال الصادرة عن "
            "البنك المركزي السعودي، مما قد يؤدي إلى عقوبات تنظيمية."
        ),
        "category": "regulatory",
        "subcategory": "AML/CTF",
        "business_unit": "Compliance",
        "business_unit_ar": "الامتثال",
        "process": "Financial Crime Operations",
        "process_ar": "عمليات الجرائم المالية",
        "root_cause": (
            "Fragmented customer data across legacy CBS; manual STR workflow; "
            "insufficient coverage of PEP and adverse media screening."
        ),
        "root_cause_ar": (
            "تجزئة بيانات العملاء عبر الأنظمة القديمة، سير عمل يدوي للإبلاغ "
            "عن العمليات المشبوهة، وتغطية غير كافية لفحص الأشخاص المعرضين سياسياً."
        ),
        "inherent_likelihood": "likely",
        "inherent_impact": "severe",
        "residual_likelihood": "possible",
        "residual_impact": "major",
        "treatment_strategy": "mitigate",
        "treatment_plan": (
            "Roll out unified customer data hub, automate STR case creation, "
            "expand screening list coverage, and conduct quarterly red-team testing."
        ),
        "treatment_plan_ar": (
            "تنفيذ مركز موحد لبيانات العملاء، أتمتة إنشاء بلاغات العمليات المشبوهة، "
            "وتوسيع تغطية قوائم الفحص، وإجراء اختبارات ربع سنوية."
        ),
        "owner": "Chief Compliance Officer",
        "owner_ar": "رئيس الامتثال",
        "status": "treating",
        "trend_direction": "improving",
    },
    {
        "seed_key": "phv-risk-sama-sanctions",
        "regulator_abbr": "SAMA",
        "title": "Sanctions Screening Gaps on UN / OFAC / GCC Lists",
        "title_ar": "ثغرات في فحص العقوبات الأممية والخليجية",
        "description": (
            "Risk of onboarding or transacting with designated persons due to "
            "stale sanctions lists, weak fuzzy matching, or delayed list updates."
        ),
        "description_ar": (
            "خطر استقبال عملاء أو تنفيذ معاملات لأشخاص مدرجين بسبب قوائم عقوبات "
            "غير محدثة أو مطابقة ضعيفة أو تأخر في تحديث القوائم."
        ),
        "category": "compliance",
        "subcategory": "Sanctions",
        "business_unit": "Compliance",
        "business_unit_ar": "الامتثال",
        "process": "Screening & Onboarding",
        "process_ar": "الفحص والتأهيل",
        "root_cause": "Daily-only list refresh; no fuzzy matching on Arabic names.",
        "root_cause_ar": "تحديث يومي فقط للقوائم، وعدم وجود مطابقة غير حادة للأسماء العربية.",
        "inherent_likelihood": "possible",
        "inherent_impact": "severe",
        "residual_likelihood": "unlikely",
        "residual_impact": "major",
        "treatment_strategy": "mitigate",
        "owner": "Head of Screening",
        "owner_ar": "مدير الفحص",
        "status": "treating",
        "trend_direction": "stable",
    },
    {
        "seed_key": "phv-risk-cma-market-conduct",
        "regulator_abbr": "CMA",
        "title": "Market Conduct & Client Asset Segregation Risk",
        "title_ar": "مخاطر السلوك في السوق وفصل أصول العملاء",
        "description": (
            "Risk of CMA enforcement action due to mishandling of client assets, "
            "inadequate suitability assessment, or misleading marketing of "
            "investment products."
        ),
        "description_ar": (
            "خطر اتخاذ هيئة السوق المالية إجراءات تنفيذية بسبب سوء التعامل مع "
            "أصول العملاء أو ضعف تقييم الملاءمة أو تسويق مضلل لمنتجات الاستثمار."
        ),
        "category": "conduct",
        "subcategory": "Market Conduct",
        "business_unit": "Capital Markets",
        "business_unit_ar": "أسواق المال",
        "process": "Client Suitability",
        "process_ar": "ملاءمة العميل",
        "inherent_likelihood": "possible",
        "inherent_impact": "major",
        "residual_likelihood": "unlikely",
        "residual_impact": "moderate",
        "treatment_strategy": "mitigate",
        "owner": "Head of Capital Markets Compliance",
        "owner_ar": "رئيس امتثال أسواق المال",
        "status": "monitoring",
        "trend_direction": "stable",
    },
    {
        "seed_key": "phv-risk-ia-solvency",
        "regulator_abbr": "IA",
        "title": "Insurance Solvency & Technical Reserves Shortfall",
        "title_ar": "نقص الملاءة المالية والاحتياطيات الفنية للتأمين",
        "description": (
            "Risk of failing Insurance Authority solvency margin requirements "
            "due to under-reserving, reinsurance recoverable issues, or claims "
            "reserve volatility."
        ),
        "description_ar": (
            "خطر الإخفاق في تلبية متطلبات هامش الملاءة المحددة من هيئة التأمين "
            "بسبب نقص الاحتياطيات أو مشاكل المبالغ المستردة من إعادة التأمين."
        ),
        "category": "financial",
        "subcategory": "Solvency",
        "business_unit": "Actuarial",
        "business_unit_ar": "الاكتواري",
        "inherent_likelihood": "possible",
        "inherent_impact": "severe",
        "residual_likelihood": "unlikely",
        "residual_impact": "major",
        "treatment_strategy": "mitigate",
        "owner": "Chief Actuary",
        "owner_ar": "رئيس الاكتواريين",
        "status": "monitoring",
        "trend_direction": "stable",
    },
    {
        "seed_key": "phv-risk-sama-cyber",
        "regulator_abbr": "SAMA",
        "title": "Cybersecurity Framework (SAMA CSF) Compliance Risk",
        "title_ar": "مخاطر الامتثال لإطار الأمن السيبراني للبنك المركزي",
        "description": (
            "Risk of gaps against SAMA Cyber Security Framework domains "
            "(Governance, Risk, Control, Compliance) leading to regulatory "
            "findings and heightened cyber-attack exposure."
        ),
        "description_ar": (
            "خطر وجود فجوات مقابل نطاقات إطار الأمن السيبراني للبنك المركزي "
            "السعودي مما يؤدي إلى ملاحظات تنظيمية وارتفاع مخاطر الهجمات السيبرانية."
        ),
        "category": "technology",
        "subcategory": "Cybersecurity",
        "business_unit": "Information Security",
        "business_unit_ar": "أمن المعلومات",
        "inherent_likelihood": "likely",
        "inherent_impact": "major",
        "residual_likelihood": "possible",
        "residual_impact": "moderate",
        "treatment_strategy": "mitigate",
        "owner": "Chief Information Security Officer",
        "owner_ar": "رئيس أمن المعلومات",
        "status": "treating",
        "trend_direction": "improving",
    },
    {
        "seed_key": "phv-risk-third-party",
        "regulator_abbr": "SAMA",
        "title": "Third-Party & Outsourcing Governance Risk",
        "title_ar": "مخاطر حوكمة الأطراف الخارجية والإسناد",
        "description": (
            "Risk that outsourced service providers (cloud, payments, screening) "
            "fail SAMA outsourcing rules, including data residency, "
            "concentration, and exit-plan requirements."
        ),
        "description_ar": (
            "خطر عدم التزام مزودي الخدمات الخارجية بقواعد الإسناد لدى البنك "
            "المركزي، بما في ذلك توطين البيانات والتركز وخطة الخروج."
        ),
        "category": "third_party",
        "subcategory": "Outsourcing",
        "business_unit": "Vendor Management",
        "business_unit_ar": "إدارة الموردين",
        "inherent_likelihood": "possible",
        "inherent_impact": "major",
        "residual_likelihood": "unlikely",
        "residual_impact": "moderate",
        "treatment_strategy": "mitigate",
        "owner": "Head of Vendor Management",
        "owner_ar": "مدير إدارة الموردين",
        "status": "treating",
        "trend_direction": "stable",
    },
    {
        "seed_key": "phv-risk-conduct-fraud",
        "regulator_abbr": "SAMA",
        "title": "Internal Fraud & Conduct Risk",
        "title_ar": "مخاطر الاحتيال الداخلي وسلوك الموظفين",
        "description": (
            "Risk of employee-originated fraud, mis-selling, or breach of code "
            "of conduct, with reputational and regulatory consequences."
        ),
        "description_ar": (
            "خطر ارتكاب الموظفين للاحتيال أو البيع المضلل أو الإخلال بمدونة "
            "السلوك، مع تبعات على السمعة والتنظيم."
        ),
        "category": "fraud",
        "subcategory": "Internal Fraud",
        "business_unit": "Human Resources",
        "business_unit_ar": "الموارد البشرية",
        "inherent_likelihood": "possible",
        "inherent_impact": "moderate",
        "residual_likelihood": "unlikely",
        "residual_impact": "moderate",
        "treatment_strategy": "mitigate",
        "owner": "Head of Operational Risk",
        "owner_ar": "رئيس المخاطر التشغيلية",
        "status": "monitoring",
        "trend_direction": "stable",
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  Issues — spanning audit / risk / compliance / regulator_note sources
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_ISSUES: list[dict] = [
    {
        "seed_key": "phv-issue-sama-str-backlog",
        "link_risk_seed": "phv-risk-sama-aml-ctf",
        "title": "STR Backlog Exceeds SAMA 7-Day Filing Expectation",
        "title_ar": "تراكم بلاغات العمليات المشبوهة يتجاوز المهلة الزمنية",
        "description": (
            "Queue of confirmed suspicious transactions pending STR filing "
            "has grown beyond the 7-day internal SLA mirroring SAMA guidance, "
            "creating regulatory filing risk."
        ),
        "description_ar": (
            "ازدادت قائمة العمليات المشبوهة المؤكدة بانتظار الإبلاغ إلى أكثر "
            "من 7 أيام وفق التوجيه الداخلي المبني على إرشادات البنك المركزي."
        ),
        "source": "compliance",
        "severity": "high",
        "status": "in_progress",
        "owner": "AML Unit Manager",
        "owner_ar": "مدير وحدة مكافحة غسل الأموال",
        "due_days": 20,
    },
    {
        "seed_key": "phv-issue-cma-suitability",
        "link_risk_seed": "phv-risk-cma-market-conduct",
        "title": "Suitability Assessment Template Missing Risk Tolerance Field",
        "title_ar": "نموذج تقييم الملاءمة لا يحتوي على حقل تحمل المخاطر",
        "description": (
            "CMA Client Suitability rules require documented risk tolerance "
            "per investor; current form captures only investment objective."
        ),
        "description_ar": (
            "تتطلب قواعد ملاءمة العميل لدى هيئة السوق المالية توثيق تحمل المخاطر "
            "لكل مستثمر، بينما النموذج الحالي يسجل هدف الاستثمار فقط."
        ),
        "source": "audit",
        "severity": "medium",
        "status": "open",
        "owner": "Head of Capital Markets Compliance",
        "owner_ar": "رئيس امتثال أسواق المال",
        "due_days": 30,
    },
    {
        "seed_key": "phv-issue-ia-reserves-lag",
        "link_risk_seed": "phv-risk-ia-solvency",
        "title": "Quarterly Technical Reserves Calculation Delayed by 10 Days",
        "title_ar": "تأخر احتساب الاحتياطيات الفنية الربع سنوية عشرة أيام",
        "description": (
            "Actuarial pipeline is 10 business days late delivering the "
            "Insurance Authority solvency submission, risking reporting breach."
        ),
        "description_ar": (
            "تأخر فريق الاكتواريين 10 أيام عمل في تسليم بيانات الملاءة المطلوبة "
            "من هيئة التأمين، مما يعرض للإخلال بالإبلاغ."
        ),
        "source": "management_review",
        "severity": "medium",
        "status": "open",
        "owner": "Chief Actuary",
        "owner_ar": "رئيس الاكتواريين",
        "due_days": 14,
    },
    {
        "seed_key": "phv-issue-sanctions-fuzzy",
        "link_risk_seed": "phv-risk-sama-sanctions",
        "title": "Arabic-Name Fuzzy Matching Not Enabled on Screening Engine",
        "title_ar": "لم يتم تفعيل المطابقة اللطيفة للأسماء العربية",
        "description": (
            "Screening engine uses exact + English-phonetic matching only; "
            "SAMA expectation is multi-script transliteration coverage."
        ),
        "description_ar": (
            "محرك الفحص يستخدم المطابقة التامة والصوتية الإنجليزية فقط؛ توقع "
            "البنك المركزي هو تغطية التحويل الحرفي بلغات متعددة."
        ),
        "source": "risk",
        "severity": "high",
        "status": "in_progress",
        "owner": "Head of Screening",
        "owner_ar": "مدير الفحص",
        "due_days": 45,
    },
    {
        "seed_key": "phv-issue-cyber-phishing",
        "link_risk_seed": "phv-risk-sama-cyber",
        "title": "Phishing Simulation Fail-Rate Above SAMA CSF Threshold",
        "title_ar": "نسبة الفشل في محاكاة التصيد أعلى من حد إطار الأمن السيبراني",
        "description": (
            "Last phishing simulation fail-rate was 14% vs the 10% internal "
            "limit aligned with SAMA Cyber Security Framework expectations."
        ),
        "description_ar": (
            "بلغت نسبة الفشل في آخر محاكاة تصيد 14% مقابل الحد الداخلي 10% "
            "المتوافق مع إطار الأمن السيبراني للبنك المركزي."
        ),
        "source": "incident",
        "severity": "medium",
        "status": "open",
        "owner": "CISO Office",
        "owner_ar": "مكتب رئيس أمن المعلومات",
        "due_days": 60,
    },
    {
        "seed_key": "phv-issue-vendor-exit",
        "link_risk_seed": "phv-risk-third-party",
        "title": "Cloud Provider Exit Plan Not Refreshed in 18 Months",
        "title_ar": "لم يتم تحديث خطة الخروج لمزود السحابة منذ 18 شهراً",
        "description": (
            "SAMA outsourcing rules require annual review of material vendor "
            "exit plans; current cloud provider plan is stale."
        ),
        "description_ar": (
            "تتطلب قواعد الإسناد للبنك المركزي مراجعة سنوية لخطط الخروج "
            "للموردين الجوهريين، والخطة الحالية لمزود السحابة قديمة."
        ),
        "source": "regulator_note",
        "severity": "low",
        "status": "open",
        "owner": "Head of Vendor Management",
        "owner_ar": "مدير إدارة الموردين",
        "due_days": 90,
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  Audit plan → engagement → findings → management responses
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_AUDIT_PLANS: list[dict] = [
    {
        "seed_key": "phv-plan-annual-fin-crime",
        "title": "Annual Financial Crime & AML Audit Plan",
        "title_ar": "خطة المراجعة السنوية للجرائم المالية ومكافحة غسل الأموال",
        "description": (
            "Risk-based annual plan covering SAMA AML/CTF, sanctions, and "
            "financial crime controls across retail and corporate banking."
        ),
        "description_ar": (
            "خطة سنوية قائمة على المخاطر تغطي ضوابط مكافحة غسل الأموال والعقوبات "
            "والجرائم المالية في كل من الخدمات المصرفية للأفراد والشركات."
        ),
        "owner": "Chief Internal Auditor",
        "owner_ar": "رئيس المراجعة الداخلية",
        "status": "in_progress",
        "period_days_start": -30,
        "period_days_end": 335,
    },
    {
        "seed_key": "phv-plan-cma-investments",
        "title": "CMA-Regulated Investment Activities Review",
        "title_ar": "مراجعة الأنشطة الاستثمارية الخاضعة لهيئة السوق المالية",
        "description": (
            "Thematic review of client suitability, custody segregation, and "
            "market conduct controls under CMA rules."
        ),
        "description_ar": (
            "مراجعة موضوعية لملاءمة العميل وفصل الحفظ وضوابط السلوك في السوق "
            "وفقاً لقواعد هيئة السوق المالية."
        ),
        "owner": "Senior Audit Manager — Capital Markets",
        "owner_ar": "مدير مراجعة أول - أسواق المال",
        "status": "approved",
        "period_days_start": 0,
        "period_days_end": 180,
    },
]


SAMPLE_ENGAGEMENTS: list[dict] = [
    {
        "seed_key": "phv-eng-cdd-deep-dive",
        "plan_seed_key": "phv-plan-annual-fin-crime",
        "title": "CDD & EDD Deep Dive — Retail Banking",
        "title_ar": "مراجعة معمقة للعناية الواجبة والمعززة - الخدمات المصرفية للأفراد",
        "scope": "Retail onboarding for the last 12 months; sample of 150 files.",
        "scope_ar": "استقبال عملاء الأفراد خلال آخر 12 شهراً، عينة من 150 ملفاً.",
        "objectives": (
            "Assess whether CDD and EDD procedures meet SAMA AML/CTF Rules and "
            "internal risk-based approach."
        ),
        "objectives_ar": (
            "تقييم مدى توافق إجراءات العناية الواجبة والمعززة مع قواعد مكافحة "
            "غسل الأموال للبنك المركزي ومبدأ المنهج القائم على المخاطر."
        ),
        "owner": "Audit Manager — Financial Crime",
        "owner_ar": "مدير مراجعة - الجرائم المالية",
        "status": "reporting",
        "start_days": -20,
        "end_days": 10,
    },
    {
        "seed_key": "phv-eng-suitability",
        "plan_seed_key": "phv-plan-cma-investments",
        "title": "Client Suitability Controls Walkthrough",
        "title_ar": "استعراض ضوابط ملاءمة العميل",
        "scope": "All active investment advisory relationships, Q1-Q2 sample.",
        "scope_ar": "جميع علاقات الاستشارات الاستثمارية النشطة، عينة الربعين الأول والثاني.",
        "objectives": (
            "Confirm that suitability assessments meet CMA Investment Business "
            "Regulations and include documented risk tolerance."
        ),
        "objectives_ar": (
            "التأكد من أن تقييمات الملاءمة تفي بلوائح أعمال الأوراق المالية "
            "الصادرة عن هيئة السوق المالية وتتضمن تحمل المخاطر الموثق."
        ),
        "owner": "Audit Senior — Capital Markets",
        "owner_ar": "مراجع أول - أسواق المال",
        "status": "fieldwork",
        "start_days": -5,
        "end_days": 40,
    },
]


SAMPLE_FINDINGS: list[dict] = [
    {
        "seed_key": "phv-find-edd-pep",
        "engagement_seed_key": "phv-eng-cdd-deep-dive",
        "title": "Enhanced Due Diligence Missing for 12% of Sampled PEPs",
        "title_ar": "عدم إجراء العناية الواجبة المعززة لـ12% من عينة الأشخاص المعرضين سياسياً",
        "description": (
            "Of 50 PEP files sampled, 6 lacked documented source-of-wealth "
            "evidence and senior management approval — inconsistent with "
            "SAMA AML/CTF Rules Art. 8 (EDD for high-risk customers)."
        ),
        "description_ar": (
            "من بين 50 ملفاً لأشخاص معرضين سياسياً، لم تتضمن 6 ملفات مصدر "
            "الثروة أو موافقة الإدارة العليا، بما لا يتوافق مع المادة 8 من "
            "قواعد مكافحة غسل الأموال للبنك المركزي."
        ),
        "severity": "high",
        "status": "in_remediation",
        "root_cause": (
            "EDD checklist not mandatory in onboarding workflow; reviewer "
            "override permitted without comment."
        ),
        "root_cause_ar": (
            "قائمة العناية الواجبة المعززة غير إلزامية في سير عمل استقبال "
            "العملاء، ويسمح بتجاوز المراجع دون تعليق."
        ),
        "owner": "Head of Retail Onboarding",
        "owner_ar": "رئيس استقبال عملاء الأفراد",
        "due_days": 45,
        "management_response": (
            "Accepted. The onboarding platform will enforce mandatory EDD "
            "checklist completion for PEPs from next release."
        ),
        "management_response_ar": (
            "مقبول. سيتم فرض إلزامية إكمال قائمة العناية الواجبة المعززة للأشخاص "
            "المعرضين سياسياً في منصة استقبال العملاء اعتباراً من الإصدار التالي."
        ),
        "response_status": "in_progress",
        "response_due_days": 30,
    },
    {
        "seed_key": "phv-find-str-timeliness",
        "engagement_seed_key": "phv-eng-cdd-deep-dive",
        "title": "STR Filing Average Turnaround of 9 Days vs 7-Day Internal SLA",
        "title_ar": "متوسط زمن الإبلاغ عن العمليات المشبوهة 9 أيام مقابل مهلة 7 أيام",
        "description": (
            "Median time between alert confirmation and STR filing was 9 days "
            "over the audit period, breaching the internal SLA aligned with "
            "SAMA expectations."
        ),
        "description_ar": (
            "متوسط الزمن بين تأكيد التنبيه والإبلاغ عن العملية المشبوهة هو 9 "
            "أيام خلال فترة المراجعة، بما يخل بالمهلة الداخلية."
        ),
        "severity": "medium",
        "status": "open",
        "root_cause": "Manual case handover; no automatic SLA tracking.",
        "root_cause_ar": "تسليم يدوي للقضايا ولا يوجد تتبع آلي للمهل.",
        "owner": "AML Unit Manager",
        "owner_ar": "مدير وحدة مكافحة غسل الأموال",
        "due_days": 60,
        "management_response": (
            "Accepted. SLA counter will be embedded in case management UI."
        ),
        "management_response_ar": (
            "مقبول. سيتم تضمين عداد المهلة في واجهة إدارة الحالات."
        ),
        "response_status": "pending",
        "response_due_days": 45,
    },
    {
        "seed_key": "phv-find-suitability-doc",
        "engagement_seed_key": "phv-eng-suitability",
        "title": "Suitability Forms Capture Objective but Omit Risk Tolerance",
        "title_ar": "نماذج الملاءمة توثق الهدف ولكن تغفل تحمل المخاطر",
        "description": (
            "Walkthrough of 20 suitability files shows no field for documented "
            "risk tolerance, conflicting with CMA Investment Business "
            "Regulations Art. 32."
        ),
        "description_ar": (
            "استعراض 20 ملف ملاءمة أظهر عدم وجود حقل لتوثيق تحمل المخاطر، "
            "بما يتعارض مع المادة 32 من لوائح أعمال الأوراق المالية لهيئة السوق المالية."
        ),
        "severity": "medium",
        "status": "open",
        "owner": "Head of Capital Markets Compliance",
        "owner_ar": "رئيس امتثال أسواق المال",
        "due_days": 50,
        "management_response": (
            "Accepted with timeline — template redesign to include risk "
            "tolerance in next release cycle."
        ),
        "management_response_ar": (
            "مقبول مع جدول زمني — إعادة تصميم النموذج لتضمين تحمل المخاطر."
        ),
        "response_status": "accepted",
        "response_due_days": 40,
    },
    {
        "seed_key": "phv-find-cyber-phishing",
        "engagement_seed_key": "phv-eng-cdd-deep-dive",
        "title": "Phishing Awareness Program Coverage Gap",
        "title_ar": "فجوة في تغطية برنامج التوعية بالتصيد",
        "description": (
            "Quarterly phishing simulation reached 82% of staff; SAMA CSF "
            "maturity expectation is ≥95% coverage for Tier-1 banks."
        ),
        "description_ar": (
            "غطت محاكاة التصيد الربع سنوية 82% من الموظفين، بينما يتوقع إطار "
            "الأمن السيبراني للبنك المركزي تغطية لا تقل عن 95% للبنوك من الفئة الأولى."
        ),
        "severity": "low",
        "status": "open",
        "owner": "CISO Office",
        "owner_ar": "مكتب رئيس أمن المعلومات",
        "due_days": 75,
        "management_response": (
            "Accepted. HR directory sync to be automated to remove coverage gap."
        ),
        "management_response_ar": (
            "مقبول. سيتم أتمتة المزامنة مع دليل الموارد البشرية لسد الفجوة."
        ),
        "response_status": "pending",
        "response_due_days": 60,
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  Remediation actions (tied to issues)
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_REMEDIATIONS: list[dict] = [
    {
        "seed_key": "phv-rem-str-automation",
        "issue_seed_key": "phv-issue-sama-str-backlog",
        "title": "Automate STR Case Creation & SLA Countdown",
        "title_ar": "أتمتة إنشاء بلاغات العمليات المشبوهة وتتبع المهلة",
        "description": (
            "Integrate alerting pipeline with case management to auto-create "
            "STR drafts and display days-remaining counter."
        ),
        "description_ar": (
            "دمج خط التنبيهات مع إدارة الحالات لإنشاء مسودات البلاغات آلياً "
            "وعرض العداد التنازلي."
        ),
        "owner": "Head of AML Tech",
        "owner_ar": "رئيس أنظمة مكافحة غسل الأموال",
        "status": "in_progress",
        "progress_pct": 45,
        "target_days": 30,
    },
    {
        "seed_key": "phv-rem-suitability-template",
        "issue_seed_key": "phv-issue-cma-suitability",
        "title": "Redesign Suitability Form with Risk-Tolerance Field",
        "title_ar": "إعادة تصميم نموذج الملاءمة بحقل تحمل المخاطر",
        "description": (
            "Update suitability template, migrate historical records with "
            "default 'needs-review' flag, and retrain RMs."
        ),
        "description_ar": (
            "تحديث نموذج الملاءمة، وترحيل السجلات السابقة مع وسم 'بحاجة إلى "
            "مراجعة'، وإعادة تدريب مديري العلاقات."
        ),
        "owner": "Head of Capital Markets Compliance",
        "owner_ar": "رئيس امتثال أسواق المال",
        "status": "not_started",
        "progress_pct": 0,
        "target_days": 40,
    },
    {
        "seed_key": "phv-rem-actuarial-pipeline",
        "issue_seed_key": "phv-issue-ia-reserves-lag",
        "title": "Re-sequence Actuarial Data Pipeline",
        "title_ar": "إعادة ترتيب خط بيانات الاكتواريين",
        "description": (
            "Move reinsurance recoverable step earlier to avoid blocking the "
            "solvency submission; add automated consistency checks."
        ),
        "description_ar": (
            "نقل خطوة المبالغ المستردة من إعادة التأمين إلى مرحلة مبكرة لتجنب "
            "تعطيل تقديم الملاءة، وإضافة فحوصات اتساق آلية."
        ),
        "owner": "Head of Actuarial Operations",
        "owner_ar": "رئيس عمليات الاكتواريين",
        "status": "in_progress",
        "progress_pct": 60,
        "target_days": 20,
    },
    {
        "seed_key": "phv-rem-fuzzy-arabic",
        "issue_seed_key": "phv-issue-sanctions-fuzzy",
        "title": "Enable Arabic Transliteration & Fuzzy Match",
        "title_ar": "تفعيل التحويل الحرفي العربي والمطابقة اللطيفة",
        "description": (
            "Tune screening engine for Arabic script plus Jaccard threshold; "
            "run back-testing against known designated persons."
        ),
        "description_ar": (
            "ضبط محرك الفحص للنص العربي مع حد جاكارد وإجراء اختبار رجعي "
            "مقابل الأشخاص المدرجين المعروفين."
        ),
        "owner": "Head of Screening",
        "owner_ar": "مدير الفحص",
        "status": "in_progress",
        "progress_pct": 25,
        "target_days": 45,
    },
    {
        "seed_key": "phv-rem-vendor-exit-refresh",
        "issue_seed_key": "phv-issue-vendor-exit",
        "title": "Refresh Cloud Provider Exit Plan",
        "title_ar": "تحديث خطة الخروج لمزود السحابة",
        "description": (
            "Run exit tabletop exercise, update RTO/RPO, and obtain Vendor "
            "Oversight Committee approval."
        ),
        "description_ar": (
            "تنفيذ تمرين مكتبي للخروج، وتحديث مؤشرات الاستعادة، والحصول على "
            "موافقة لجنة الإشراف على الموردين."
        ),
        "owner": "Head of Vendor Management",
        "owner_ar": "مدير إدارة الموردين",
        "status": "not_started",
        "progress_pct": 0,
        "target_days": 90,
    },
    {
        "seed_key": "phv-rem-phishing-coverage",
        "issue_seed_key": "phv-issue-cyber-phishing",
        "title": "Automate HR Directory Sync for Phishing Simulations",
        "title_ar": "أتمتة المزامنة مع دليل الموارد البشرية لمحاكاة التصيد",
        "description": (
            "Connect phishing platform to HR master data nightly; track "
            "coverage vs 95% threshold."
        ),
        "description_ar": (
            "ربط منصة التصيد بالبيانات الرئيسية للموارد البشرية بشكل ليلي "
            "وتتبع التغطية مقابل الحد 95%."
        ),
        "owner": "CISO Office",
        "owner_ar": "مكتب رئيس أمن المعلومات",
        "status": "in_progress",
        "progress_pct": 30,
        "target_days": 60,
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  Unified GRC actions (Phase G3 surface)
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_GRC_ACTIONS: list[dict] = [
    {
        "seed_key": "phv-act-board-risk-brief",
        "source_type": "risk",
        "source_seed_key": "phv-risk-sama-aml-ctf",
        "title": "Prepare Board Risk Committee Brief on AML Remediation",
        "title_ar": "إعداد موجز للجنة المخاطر في مجلس الإدارة عن معالجة مكافحة غسل الأموال",
        "priority": "high",
        "status": "open",
        "owner": "Chief Compliance Officer",
        "owner_ar": "رئيس الامتثال",
        "due_days": 14,
        "reason": "Quarterly board oversight covering SAMA engagement outcomes.",
        "reason_ar": "رقابة مجلس الإدارة الربع سنوية لنتائج التواصل مع البنك المركزي.",
    },
    {
        "seed_key": "phv-act-cma-training",
        "source_type": "issue",
        "source_seed_key": "phv-issue-cma-suitability",
        "title": "Run CMA Suitability Refresher for Relationship Managers",
        "title_ar": "تنظيم تدريب تنشيطي للملاءمة مع مديري العلاقات",
        "priority": "medium",
        "status": "open",
        "owner": "Head of Capital Markets Compliance",
        "owner_ar": "رئيس امتثال أسواق المال",
        "due_days": 35,
        "reason": "Mitigates re-occurrence once the form redesign lands.",
        "reason_ar": "يحد من تكرار الحالة بعد إعادة تصميم النموذج.",
    },
    {
        "seed_key": "phv-act-ia-solvency-signoff",
        "source_type": "risk",
        "source_seed_key": "phv-risk-ia-solvency",
        "title": "Obtain CFO & Chief Actuary Sign-off on Q-End Solvency Pack",
        "title_ar": "الحصول على اعتماد المدير المالي ورئيس الاكتواريين على حزمة الملاءة",
        "priority": "critical",
        "status": "in_progress",
        "owner": "Head of Actuarial Operations",
        "owner_ar": "رئيس عمليات الاكتواريين",
        "due_days": 10,
        "reason": "IA submission requires dual sign-off.",
        "reason_ar": "يتطلب التقديم لهيئة التأمين اعتماد مزدوج.",
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  Service
# ══════════════════════════════════════════════════════════════════════════


class PhaseVSeedService:
    """Idempotent loader for realistic Phase V GRC sample data."""

    @staticmethod
    async def _find_existing(db: AsyncSession, model, seed_key: str, *, title: Optional[str] = None):
        """Find a row previously created by this seed service.

        Most GRC tables expose a JSON ``tags`` column we can piggyback on.
        ``EnterpriseRisk`` uses ``risk_factors`` instead.  ``AuditPlan`` has
        neither, so we fall back to an exact-title match for it.
        """
        if model is AuditPlan:
            if title is None:
                return None
            result = await db.execute(select(model).where(model.title == title))
            return result.scalars().first()

        attr = "risk_factors" if model is EnterpriseRisk else "tags"
        result = await db.execute(select(model))
        for row in result.scalars().all():
            bag = getattr(row, attr, None) or {}
            if isinstance(bag, dict) and bag.get("seed_key") == seed_key:
                return row
        return None

    @staticmethod
    async def seed_all(db: AsyncSession) -> dict:
        stats = {
            "risks_created": 0,
            "issues_created": 0,
            "remediations_created": 0,
            "audit_plans_created": 0,
            "audit_engagements_created": 0,
            "audit_findings_created": 0,
            "management_responses_created": 0,
            "grc_actions_created": 0,
        }

        reg_rows = (await db.execute(select(Regulator))).scalars().all()
        regulators = {r.abbreviation.upper(): r.id for r in reg_rows}

        # ── Risks ───────────────────────────────────────────────────────
        risk_id_by_seed: dict[str, str] = {}
        for r in SAMPLE_RISKS:
            existing = await PhaseVSeedService._find_existing(
                db, EnterpriseRisk, r["seed_key"]
            )
            if existing:
                risk_id_by_seed[r["seed_key"]] = existing.id
                continue

            inherent_likelihood = LikelihoodLevel(r["inherent_likelihood"])
            inherent_impact = ImpactLevel(r["inherent_impact"])
            residual_likelihood = LikelihoodLevel(r["residual_likelihood"])
            residual_impact = ImpactLevel(r["residual_impact"])

            risk = EnterpriseRisk(
                id=generate_uuid(),
                title=r["title"],
                title_ar=r.get("title_ar"),
                description=r["description"],
                description_ar=r.get("description_ar"),
                category=RiskCategoryEnum(r["category"]),
                subcategory=r.get("subcategory"),
                business_unit=r.get("business_unit"),
                business_unit_ar=r.get("business_unit_ar"),
                process=r.get("process"),
                process_ar=r.get("process_ar"),
                regulator_id=regulators.get((r.get("regulator_abbr") or "").upper()),
                root_cause=r.get("root_cause"),
                root_cause_ar=r.get("root_cause_ar"),
                inherent_likelihood=inherent_likelihood,
                inherent_impact=inherent_impact,
                inherent_score=compute_risk_score(inherent_likelihood, inherent_impact),
                residual_likelihood=residual_likelihood,
                residual_impact=residual_impact,
                residual_score=compute_risk_score(residual_likelihood, residual_impact),
                treatment_strategy=TreatmentStrategy(r.get("treatment_strategy", "mitigate")),
                treatment_plan=r.get("treatment_plan"),
                treatment_plan_ar=r.get("treatment_plan_ar"),
                owner=r.get("owner"),
                owner_ar=r.get("owner_ar"),
                status=RiskStatus(r.get("status", "identified")),
                trend_direction=TrendDirection(r.get("trend_direction", "new")),
                risk_factors={"seed_source": "phase_v"},
            )
            # EnterpriseRisk has no `tags` column; we piggyback on risk_factors
            risk.risk_factors = {"seed_key": r["seed_key"], "seed_source": "phase_v"}
            db.add(risk)
            await db.flush()
            risk_id_by_seed[r["seed_key"]] = risk.id
            stats["risks_created"] += 1

        # Risks don't have a tags column, so idempotency check uses risk_factors
        # Override the _find_existing helper specifically for EnterpriseRisk:
        # (handled below — on re-run, existing rows above would miss the tag,
        # so we additionally scan by title as a fallback)
        result = await db.execute(select(EnterpriseRisk))
        for risk in result.scalars().all():
            rf = risk.risk_factors or {}
            if isinstance(rf, dict) and rf.get("seed_key"):
                risk_id_by_seed.setdefault(rf["seed_key"], risk.id)

        # ── Issues & Remediations ──────────────────────────────────────
        issue_id_by_seed: dict[str, str] = {}
        for i in SAMPLE_ISSUES:
            existing = await PhaseVSeedService._find_existing(db, Issue, i["seed_key"])
            if existing:
                issue_id_by_seed[i["seed_key"]] = existing.id
                continue
            issue = Issue(
                id=generate_uuid(),
                title=i["title"],
                title_ar=i.get("title_ar"),
                description=i["description"],
                description_ar=i.get("description_ar"),
                source=IssueSource(i["source"]),
                severity=IssueSeverity(i["severity"]),
                status=IssueStatus(i["status"]),
                escalation_status=EscalationStatus.NONE,
                risk_id=risk_id_by_seed.get(i.get("link_risk_seed", "")),
                owner=i.get("owner"),
                owner_ar=i.get("owner_ar"),
                due_date=_days(i.get("due_days", 30)),
                tags={"seed_key": i["seed_key"], "seed_source": "phase_v"},
            )
            db.add(issue)
            await db.flush()
            issue_id_by_seed[i["seed_key"]] = issue.id
            stats["issues_created"] += 1

        for rem in SAMPLE_REMEDIATIONS:
            issue_id = issue_id_by_seed.get(rem["issue_seed_key"])
            if not issue_id:
                continue
            # Check if any remediation on this issue already carries our seed_key
            existing_result = await db.execute(
                select(RemediationAction).where(RemediationAction.issue_id == issue_id)
            )
            already = any(
                (ra.blockers or "").startswith(f"[seed:{rem['seed_key']}]")
                for ra in existing_result.scalars().all()
            )
            if already:
                continue
            action = RemediationAction(
                id=generate_uuid(),
                issue_id=issue_id,
                title=rem["title"],
                title_ar=rem.get("title_ar"),
                description=rem["description"],
                description_ar=rem.get("description_ar"),
                owner=rem.get("owner"),
                owner_ar=rem.get("owner_ar"),
                target_date=_days(rem.get("target_days", 45)),
                status=RemediationStatus(rem.get("status", "not_started")),
                progress_pct=int(rem.get("progress_pct", 0)),
                blockers=f"[seed:{rem['seed_key']}]",
            )
            db.add(action)
            stats["remediations_created"] += 1

        await db.flush()

        # ── Audit plans ────────────────────────────────────────────────
        plan_id_by_seed: dict[str, str] = {}
        for p in SAMPLE_AUDIT_PLANS:
            existing = await PhaseVSeedService._find_existing(
                db, AuditPlan, p["seed_key"], title=p["title"]
            )
            if existing:
                plan_id_by_seed[p["seed_key"]] = existing.id
                continue
            plan = AuditPlan(
                id=generate_uuid(),
                title=p["title"],
                title_ar=p.get("title_ar"),
                description=p.get("description"),
                description_ar=p.get("description_ar"),
                period_start=_days(p.get("period_days_start", -30)),
                period_end=_days(p.get("period_days_end", 335)),
                owner=p.get("owner"),
                owner_ar=p.get("owner_ar"),
                status=AuditPlanStatus(p.get("status", "draft")),
            )
            db.add(plan)
            await db.flush()
            plan_id_by_seed[p["seed_key"]] = plan.id
            stats["audit_plans_created"] += 1

        # ── Audit engagements ─────────────────────────────────────────
        engagement_id_by_seed: dict[str, str] = {}
        for e in SAMPLE_ENGAGEMENTS:
            plan_id = plan_id_by_seed.get(e.get("plan_seed_key", ""))
            if not plan_id:
                continue
            existing = await PhaseVSeedService._find_existing(
                db, AuditEngagement, e["seed_key"]
            )
            if existing:
                engagement_id_by_seed[e["seed_key"]] = existing.id
                continue
            eng = AuditEngagement(
                id=generate_uuid(),
                plan_id=plan_id,
                title=e["title"],
                title_ar=e.get("title_ar"),
                scope=e.get("scope"),
                scope_ar=e.get("scope_ar"),
                objectives=e.get("objectives"),
                objectives_ar=e.get("objectives_ar"),
                owner=e.get("owner"),
                owner_ar=e.get("owner_ar"),
                status=EngagementStatus(e.get("status", "planned")),
                start_date=_days(e.get("start_days", -5)),
                end_date=_days(e.get("end_days", 30)),
                tags={"seed_key": e["seed_key"], "seed_source": "phase_v"},
            )
            db.add(eng)
            await db.flush()
            engagement_id_by_seed[e["seed_key"]] = eng.id
            stats["audit_engagements_created"] += 1

        # ── Audit findings + management responses ─────────────────────
        for f in SAMPLE_FINDINGS:
            eng_id = engagement_id_by_seed.get(f.get("engagement_seed_key", ""))
            if not eng_id:
                continue
            existing = await PhaseVSeedService._find_existing(
                db, AuditFinding, f["seed_key"]
            )
            if existing:
                continue
            finding = AuditFinding(
                id=generate_uuid(),
                engagement_id=eng_id,
                title=f["title"],
                title_ar=f.get("title_ar"),
                description=f["description"],
                description_ar=f.get("description_ar"),
                severity=FindingSeverity(f.get("severity", "medium")),
                status=FindingStatus(f.get("status", "open")),
                root_cause=f.get("root_cause"),
                root_cause_ar=f.get("root_cause_ar"),
                owner=f.get("owner"),
                owner_ar=f.get("owner_ar"),
                due_date=_days(f.get("due_days", 60)),
                tags={"seed_key": f["seed_key"], "seed_source": "phase_v"},
            )
            db.add(finding)
            await db.flush()
            stats["audit_findings_created"] += 1

            if f.get("management_response"):
                response = ManagementResponse(
                    id=generate_uuid(),
                    finding_id=finding.id,
                    response_text=f["management_response"],
                    response_text_ar=f.get("management_response_ar"),
                    owner=f.get("owner"),
                    owner_ar=f.get("owner_ar"),
                    due_date=_days(f.get("response_due_days", 45)),
                    status=ResponseStatus(f.get("response_status", "pending")),
                )
                db.add(response)
                stats["management_responses_created"] += 1

        await db.flush()

        # ── Unified GRC actions ───────────────────────────────────────
        for a in SAMPLE_GRC_ACTIONS:
            existing = await PhaseVSeedService._find_existing(
                db, GRCAction, a["seed_key"]
            )
            if existing:
                continue

            source_id: Optional[str] = None
            if a["source_type"] == "risk":
                source_id = risk_id_by_seed.get(a.get("source_seed_key", ""))
            elif a["source_type"] == "issue":
                source_id = issue_id_by_seed.get(a.get("source_seed_key", ""))

            action = GRCAction(
                id=generate_uuid(),
                title=a["title"],
                title_ar=a.get("title_ar"),
                reason=a.get("reason"),
                reason_ar=a.get("reason_ar"),
                source_type=ActionSourceType(a["source_type"]),
                source_id=source_id,
                source_title=a["title"][:200],
                origin=ActionOrigin.MANUAL,
                priority=ActionPriority(a.get("priority", "medium")),
                status=ActionStatus(a.get("status", "open")),
                owner=a.get("owner"),
                owner_ar=a.get("owner_ar"),
                due_date=_days(a.get("due_days", 30)),
                tags={"seed_key": a["seed_key"], "seed_source": "phase_v"},
            )
            db.add(action)
            stats["grc_actions_created"] += 1

        await db.flush()

        logger.info("Phase V seed complete: %s", stats)
        return stats
