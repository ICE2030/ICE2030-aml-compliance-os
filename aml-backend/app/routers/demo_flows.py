"""Demo flows + Phase V seed loader endpoints.

Exposes:
- The curated demo flows (compliance / risk / audit) as structured JSON.
- An idempotent `POST /api/demo/load-samples` helper for admins so the
  frontend "Load sample data" button has a single entry point.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.grc.phase_v_seed_service import PhaseVSeedService
from app.services.usage_service import UsageService

router = APIRouter(prefix="/api/demo", tags=["Demo & Onboarding"])


DEMO_FLOWS: list[dict] = [
    {
        "key": "compliance",
        "title_en": "Regulatory Compliance Flow",
        "title_ar": "تدفق الامتثال التنظيمي",
        "description_en": (
            "Trace any regulatory obligation end-to-end: from the original "
            "source, through obligations and controls, to evidence, risk, and "
            "a resulting remediation action."
        ),
        "description_ar": (
            "تتبع أي التزام تنظيمي من المصدر مروراً بالالتزامات والضوابط "
            "وصولاً إلى الأدلة والمخاطر والإجراء المعالِج."
        ),
        "steps": [
            {
                "title_en": "1. Find the source",
                "title_ar": "1. ابحث عن المصدر",
                "path": "/reg-search",
                "hint_en": "Search SAMA / CMA / IA provisions.",
                "hint_ar": "ابحث في نصوص البنك المركزي وهيئة السوق المالية وهيئة التأمين.",
            },
            {
                "title_en": "2. Inspect the obligation",
                "title_ar": "2. راجع الالتزام",
                "path": "/review-queue",
                "hint_en": "Confirm extraction and human-in-the-loop review.",
                "hint_ar": "تأكد من الاستخلاص ومراجعة الإنسان في الحلقة.",
            },
            {
                "title_en": "3. Linked control",
                "title_ar": "3. الضابط المرتبط",
                "path": "/controls",
                "hint_en": "Every obligation maps to at least one active control.",
                "hint_ar": "كل التزام يرتبط بضابط نشط على الأقل.",
            },
            {
                "title_en": "4. Evidence of operation",
                "title_ar": "4. دليل التطبيق",
                "path": "/evidence",
                "hint_en": "Check that control evidence exists and is current.",
                "hint_ar": "تحقق من وجود أدلة الضوابط وتحديثها.",
            },
            {
                "title_en": "5. Residual risk",
                "title_ar": "5. المخاطر المتبقية",
                "path": "/grc/risks",
                "hint_en": "See how the obligation rolls up to enterprise risk.",
                "hint_ar": "شاهد كيف ينعكس الالتزام على المخاطر المؤسسية.",
            },
            {
                "title_en": "6. Action needed",
                "title_ar": "6. الإجراء المطلوب",
                "path": "/grc/actions",
                "hint_en": "Confirm there is a concrete remediation action.",
                "hint_ar": "تأكد من وجود إجراء معالج محدد.",
            },
        ],
    },
    {
        "key": "risk",
        "title_en": "Risk-to-Action Flow",
        "title_ar": "تدفق المخاطر إلى الإجراء",
        "description_en": (
            "Enterprise risk → related issue → remediation plan → tracked "
            "GRC action. Used by risk owners to prove control-effectiveness."
        ),
        "description_ar": (
            "المخاطر المؤسسية ← القضية المرتبطة ← خطة المعالجة ← الإجراء المتابَع. "
            "يستخدمه أصحاب المخاطر لإثبات فاعلية الضوابط."
        ),
        "steps": [
            {
                "title_en": "1. Risk register",
                "title_ar": "1. سجل المخاطر",
                "path": "/grc/risks",
                "hint_en": "Open a high-residual risk in the register.",
                "hint_ar": "افتح مخاطرة ذات درجة متبقية عالية.",
            },
            {
                "title_en": "2. Linked issue",
                "title_ar": "2. القضية المرتبطة",
                "path": "/grc/issues",
                "hint_en": "Drill from the risk into its open issues.",
                "hint_ar": "انتقل من المخاطرة إلى القضايا المفتوحة.",
            },
            {
                "title_en": "3. Remediation plan",
                "title_ar": "3. خطة المعالجة",
                "path": "/grc/remediation",
                "hint_en": "Review remediation owner, progress, and target date.",
                "hint_ar": "راجع المالك والتقدم والتاريخ المستهدف للمعالجة.",
            },
            {
                "title_en": "4. Unified action",
                "title_ar": "4. الإجراء الموحد",
                "path": "/grc/actions",
                "hint_en": "See the action tile surfaced on the GRC dashboard.",
                "hint_ar": "شاهد الإجراء في لوحة الحوكمة.",
            },
        ],
    },
    {
        "key": "audit",
        "title_en": "Internal Audit Flow",
        "title_ar": "تدفق المراجعة الداخلية",
        "description_en": (
            "Risk-based audit plan → engagement → control test → finding → "
            "management response. Mirrors the IIA standard narrative."
        ),
        "description_ar": (
            "خطة مراجعة قائمة على المخاطر ← مهمة ← اختبار ضابط ← ملاحظة ← "
            "رد الإدارة. يحاكي السرد المعياري لمعهد المراجعين الداخليين."
        ),
        "steps": [
            {
                "title_en": "1. Audit plan",
                "title_ar": "1. خطة المراجعة",
                "path": "/grc/audit-plans",
                "hint_en": "Start from the annual or thematic plan.",
                "hint_ar": "ابدأ من الخطة السنوية أو الموضوعية.",
            },
            {
                "title_en": "2. Engagement",
                "title_ar": "2. المهمة",
                "path": "/grc/audit-engagements",
                "hint_en": "Pick an in-flight engagement.",
                "hint_ar": "اختر مهمة قيد التنفيذ.",
            },
            {
                "title_en": "3. Control test",
                "title_ar": "3. اختبار الضابط",
                "path": "/grc/control-tests",
                "hint_en": "Inspect design + operating test results.",
                "hint_ar": "افحص نتائج اختبار التصميم والتشغيل.",
            },
            {
                "title_en": "4. Finding",
                "title_ar": "4. الملاحظة",
                "path": "/grc/audit-findings",
                "hint_en": "Open a sample finding and its severity.",
                "hint_ar": "افتح نموذجاً من الملاحظات ودرجتها.",
            },
            {
                "title_en": "5. Management response",
                "title_ar": "5. رد الإدارة",
                "path": "/grc/audit-findings",
                "hint_en": "Review accepted response and due date.",
                "hint_ar": "راجع الرد المقبول والتاريخ المستهدف.",
            },
        ],
    },
]


@router.get("/flows")
async def list_demo_flows(current_user: User = Depends(get_current_user)):
    """Return the structured demo flows used by the in-app guide."""
    return {"flows": DEMO_FLOWS}


@router.post("/load-samples")
async def load_sample_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER)
    ),
):
    """Idempotent loader for the Phase V realistic sample dataset."""
    stats = await PhaseVSeedService.seed_all(db)
    await UsageService.record_event_safely(
        db,
        event_type="seed_load",
        user_id=current_user.id,
        resource_type="phase_v_seed",
        metadata={"stats": stats},
    )
    await db.commit()
    return {"status": "ok", "stats": stats}
