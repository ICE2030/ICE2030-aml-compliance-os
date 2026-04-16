"""Compliance Knowledge Base Service for SAMA and CMA regulations.
Provides structured regulatory knowledge and answers compliance inquiries
referencing official SAMA (Saudi Central Bank) and CMA (Capital Market Authority) sources.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# SAMA (Saudi Central Bank) Regulatory Knowledge Base
SAMA_KNOWLEDGE_BASE = {
    "meta": {
        "source": "Saudi Central Bank (SAMA)",
        "source_ar": "البنك المركزي السعودي (ساما)",
        "website": "https://www.sama.gov.sa",
        "rulebook_url": "https://rulebook.sama.gov.sa",
        "aml_guide_url": "https://www.sama.gov.sa/en-US/Laws/BankingRules/The%20Anti-Money%20Laundering%20and%20Counter-Terrorism%20Financing%20AML%20-%20CTF%20Guide.pdf",
    },
    "regulations": [
        {
            "id": "SAMA-AML-001",
            "title": "Anti-Money Laundering Law (2017)",
            "title_ar": "نظام مكافحة غسل الأموال (2017)",
            "category": "aml",
            "summary": "The primary legislation for combating money laundering in Saudi Arabia. Mandates financial institutions to implement customer due diligence, maintain records, and report suspicious transactions.",
            "summary_ar": "التشريع الرئيسي لمكافحة غسل الأموال في المملكة العربية السعودية. يُلزم المؤسسات المالية بتنفيذ العناية الواجبة بالعملاء والاحتفاظ بالسجلات والإبلاغ عن المعاملات المشبوهة.",
            "key_requirements": [
                "Customer Due Diligence (CDD) for all clients",
                "Enhanced Due Diligence (EDD) for high-risk clients",
                "Suspicious Transaction Reports (STRs) to SAFIU",
                "Record keeping for minimum 10 years",
                "Staff training on AML procedures",
                "Appointment of Compliance Officer",
            ],
            "key_requirements_ar": [
                "العناية الواجبة بالعملاء لجميع العملاء",
                "العناية الواجبة المعززة للعملاء ذوي المخاطر العالية",
                "تقارير المعاملات المشبوهة إلى وحدة التحريات المالية",
                "حفظ السجلات لمدة لا تقل عن 10 سنوات",
                "تدريب الموظفين على إجراءات مكافحة غسل الأموال",
                "تعيين مسؤول الالتزام",
            ],
            "penalties": "Imprisonment up to 15 years and/or fines up to SAR 7 million",
            "reference_url": "https://rulebook.sama.gov.sa/en/node/5534",
        },
        {
            "id": "SAMA-CTF-001",
            "title": "Combating Terrorism and Financing of Terrorism Law (2017)",
            "title_ar": "نظام مكافحة الإرهاب وتمويله (2017)",
            "category": "ctf",
            "summary": "Criminalizes the financing of terrorism and mandates financial institutions to report transactions suspected to be linked to terrorist activities.",
            "summary_ar": "يُجرّم تمويل الإرهاب ويُلزم المؤسسات المالية بالإبلاغ عن المعاملات المشتبه في ارتباطها بالأنشطة الإرهابية.",
            "key_requirements": [
                "Report terrorism-related suspicious transactions",
                "Freeze assets of designated persons/entities",
                "Implement UN Security Council sanctions",
                "Cooperation with competent authorities",
            ],
            "key_requirements_ar": [
                "الإبلاغ عن المعاملات المشبوهة المتعلقة بالإرهاب",
                "تجميد أصول الأشخاص/الكيانات المصنفة",
                "تنفيذ عقوبات مجلس الأمن الدولي",
                "التعاون مع الجهات المختصة",
            ],
            "penalties": "Imprisonment up to 30 years and significant fines",
            "reference_url": "https://rulebook.sama.gov.sa/en/e-compliance-anti-money-laundering-and-combating-terrorism-financing-amlctf",
        },
        {
            "id": "SAMA-CDD-001",
            "title": "Customer Due Diligence Requirements",
            "title_ar": "متطلبات العناية الواجبة بالعملاء",
            "category": "kyc",
            "summary": "SAMA mandates comprehensive CDD procedures including identity verification, beneficial ownership identification, and ongoing monitoring.",
            "summary_ar": "يُلزم البنك المركزي السعودي بإجراءات شاملة للعناية الواجبة بالعملاء تشمل التحقق من الهوية وتحديد المالكين المستفيدين والمراقبة المستمرة.",
            "key_requirements": [
                "Verify customer identity using reliable documents",
                "Identify and verify beneficial owners (25%+ ownership threshold)",
                "Understand purpose and nature of business relationship",
                "Ongoing monitoring of transactions",
                "Enhanced measures for PEPs (Politically Exposed Persons)",
                "Risk-based approach to CDD",
            ],
            "key_requirements_ar": [
                "التحقق من هوية العميل باستخدام مستندات موثوقة",
                "تحديد والتحقق من المالكين المستفيدين (حد ملكية 25%+)",
                "فهم الغرض وطبيعة علاقة العمل",
                "المراقبة المستمرة للمعاملات",
                "إجراءات معززة للأشخاص المعرضين سياسياً",
                "نهج قائم على المخاطر للعناية الواجبة",
            ],
            "reference_url": "https://www.sama.gov.sa/en-US/Laws/BankingRules/The%20Anti-Money%20Laundering%20and%20Counter-Terrorism%20Financing%20AML%20-%20CTF%20Guide.pdf",
        },
        {
            "id": "SAMA-STR-001",
            "title": "Suspicious Transaction Reporting",
            "title_ar": "الإبلاغ عن المعاملات المشبوهة",
            "category": "reporting",
            "summary": "Financial institutions must report suspicious transactions to the Saudi Arabia Financial Intelligence Unit (SAFIU) without delay.",
            "summary_ar": "يجب على المؤسسات المالية الإبلاغ عن المعاملات المشبوهة لوحدة التحريات المالية السعودية دون تأخير.",
            "key_requirements": [
                "Report to SAFIU without delay when suspicion arises",
                "No tipping off - do not inform the customer",
                "Maintain internal records of all STRs",
                "Include all relevant transaction details",
                "Follow up reports when additional information becomes available",
                "Annual reporting statistics to SAMA",
            ],
            "key_requirements_ar": [
                "الإبلاغ لوحدة التحريات المالية فوراً عند نشوء الاشتباه",
                "عدم إبلاغ العميل - حظر الإفصاح",
                "الاحتفاظ بسجلات داخلية لجميع تقارير المعاملات المشبوهة",
                "تضمين جميع تفاصيل المعاملة ذات الصلة",
                "تقارير المتابعة عند توفر معلومات إضافية",
                "إحصائيات التقارير السنوية إلى ساما",
            ],
            "reference_url": "https://rulebook.sama.gov.sa/en/node/5534",
        },
        {
            "id": "SAMA-FINTECH-001",
            "title": "Fintech Regulatory Sandbox & Licensing",
            "title_ar": "البيئة التجريبية التنظيمية للتقنية المالية والترخيص",
            "category": "fintech",
            "summary": "SAMA operates a regulatory sandbox for fintech companies and issues Payment Service Provider licenses. All fintech companies must comply with AML/CTF requirements.",
            "summary_ar": "يدير البنك المركزي السعودي بيئة تجريبية تنظيمية لشركات التقنية المالية ويصدر تراخيص مقدمي خدمات الدفع. يجب على جميع شركات التقنية المالية الالتزام بمتطلبات مكافحة غسل الأموال وتمويل الإرهاب.",
            "key_requirements": [
                "Apply for SAMA sandbox or full license",
                "Implement full AML/CTF compliance program",
                "Appoint MLRO (Money Laundering Reporting Officer)",
                "Transaction monitoring systems required",
                "Regular compliance reporting to SAMA",
                "Data localization requirements (data must remain in KSA)",
            ],
            "key_requirements_ar": [
                "التقدم لبيئة ساما التجريبية أو الترخيص الكامل",
                "تنفيذ برنامج كامل للالتزام بمكافحة غسل الأموال وتمويل الإرهاب",
                "تعيين مسؤول الإبلاغ عن غسل الأموال",
                "أنظمة مراقبة المعاملات مطلوبة",
                "تقارير الالتزام الدورية إلى ساما",
                "متطلبات توطين البيانات (يجب أن تبقى البيانات في المملكة)",
            ],
            "reference_url": "https://www.sama.gov.sa/en-US/Fintech/Pages/default.aspx",
        },
        {
            "id": "SAMA-PDPL-001",
            "title": "Personal Data Protection Law (PDPL) Compliance",
            "title_ar": "الالتزام بنظام حماية البيانات الشخصية",
            "category": "data_protection",
            "summary": "Saudi Arabia's PDPL requires organizations to protect personal data, obtain consent for processing, and implement appropriate security measures.",
            "summary_ar": "يتطلب نظام حماية البيانات الشخصية في المملكة العربية السعودية من المنظمات حماية البيانات الشخصية والحصول على الموافقة للمعالجة وتنفيذ التدابير الأمنية المناسبة.",
            "key_requirements": [
                "Obtain consent before processing personal data",
                "Data minimization principle",
                "Right to access, correct, and delete personal data",
                "Data breach notification within 72 hours",
                "Data Protection Impact Assessments for high-risk processing",
                "Cross-border transfer restrictions",
            ],
            "key_requirements_ar": [
                "الحصول على الموافقة قبل معالجة البيانات الشخصية",
                "مبدأ تقليل البيانات",
                "الحق في الوصول والتصحيح وحذف البيانات الشخصية",
                "الإخطار بخرق البيانات خلال 72 ساعة",
                "تقييمات تأثير حماية البيانات للمعالجة عالية المخاطر",
                "قيود النقل عبر الحدود",
            ],
            "reference_url": "https://sdaia.gov.sa/en/SDAIA/aboutSDGIA/Pages/PDPL.aspx",
        },
    ],
}

# CMA (Capital Market Authority) Regulatory Knowledge Base
CMA_KNOWLEDGE_BASE = {
    "meta": {
        "source": "Capital Market Authority (CMA)",
        "source_ar": "هيئة السوق المالية",
        "website": "https://cma.org.sa",
        "regulations_url": "https://cma.org.sa/en/RulesRegulations/Regulations/Pages/default.aspx",
    },
    "regulations": [
        {
            "id": "CMA-AML-001",
            "title": "AML/CTF Guidelines for Capital Market Institutions",
            "title_ar": "إرشادات مكافحة غسل الأموال وتمويل الإرهاب لمؤسسات السوق المالية",
            "category": "aml",
            "summary": "CMA issues specific AML/CTF guidelines for securities firms, asset managers, and other capital market institutions. These complement SAMA's banking regulations.",
            "summary_ar": "تصدر هيئة السوق المالية إرشادات محددة لمكافحة غسل الأموال وتمويل الإرهاب لشركات الأوراق المالية ومديري الأصول ومؤسسات السوق المالية الأخرى.",
            "key_requirements": [
                "CDD procedures for investment account opening",
                "Risk-based client classification",
                "Transaction monitoring for securities trading",
                "STR reporting for capital market transactions",
                "Record keeping per CMA requirements",
                "Annual compliance audit",
            ],
            "key_requirements_ar": [
                "إجراءات العناية الواجبة لفتح حسابات الاستثمار",
                "تصنيف العملاء على أساس المخاطر",
                "مراقبة المعاملات لتداول الأوراق المالية",
                "الإبلاغ عن المعاملات المشبوهة لمعاملات السوق المالية",
                "حفظ السجلات وفقاً لمتطلبات الهيئة",
                "تدقيق الالتزام السنوي",
            ],
            "reference_url": "https://cma.org.sa/en/RulesRegulations/Regulations/Pages/default.aspx",
        },
        {
            "id": "CMA-FINTECH-001",
            "title": "FinTech Experimental Permit (ExPermit) Instructions",
            "title_ar": "تعليمات تصريح التجربة للتقنية المالية",
            "category": "fintech",
            "summary": "CMA provides a FinTech Lab for testing innovative financial products. Companies must obtain an ExPermit before offering fintech services in the capital market.",
            "summary_ar": "توفر هيئة السوق المالية مختبراً للتقنية المالية لاختبار المنتجات المالية المبتكرة. يجب على الشركات الحصول على تصريح التجربة قبل تقديم خدمات التقنية المالية في السوق المالية.",
            "key_requirements": [
                "Apply for FinTech ExPermit through CMA portal",
                "Demonstrate innovative fintech product/service",
                "Limited testing period with defined parameters",
                "Client protection measures required",
                "Transition to full license after successful testing",
                "IT security and data protection requirements",
            ],
            "key_requirements_ar": [
                "التقدم لتصريح التجربة عبر بوابة الهيئة",
                "إثبات منتج/خدمة تقنية مالية مبتكرة",
                "فترة اختبار محدودة بمعايير محددة",
                "متطلبات حماية العملاء",
                "الانتقال للترخيص الكامل بعد الاختبار الناجح",
                "متطلبات أمن تقنية المعلومات وحماية البيانات",
            ],
            "reference_url": "https://cma.gov.sa/en/RulesRegulations/Regulations/Documents/FinTech_en.pdf",
        },
        {
            "id": "CMA-INST-001",
            "title": "Capital Market Institutions Regulations",
            "title_ar": "لائحة مؤسسات السوق المالية",
            "category": "licensing",
            "summary": "Comprehensive regulations governing the licensing, operation, and compliance requirements of capital market institutions in Saudi Arabia.",
            "summary_ar": "لوائح شاملة تحكم الترخيص والتشغيل ومتطلبات الالتزام لمؤسسات السوق المالية في المملكة العربية السعودية.",
            "key_requirements": [
                "Authorization from CMA for securities activities",
                "Fit and proper criteria for key personnel",
                "Minimum capital requirements",
                "Compliance function and reporting",
                "Risk management framework",
                "Client money and asset protection",
            ],
            "key_requirements_ar": [
                "ترخيص من الهيئة لأنشطة الأوراق المالية",
                "معايير الأهلية والملاءمة للموظفين الرئيسيين",
                "الحد الأدنى لمتطلبات رأس المال",
                "وظيفة الالتزام وإعداد التقارير",
                "إطار إدارة المخاطر",
                "حماية أموال وأصول العملاء",
            ],
            "reference_url": "https://cma.gov.sa/en/RulesRegulations/Regulations/Documents/CapitalMarketInstitutionsRegulations.pdf",
        },
        {
            "id": "CMA-ROBO-001",
            "title": "Robo-Advisory Regulatory Framework",
            "title_ar": "الإطار التنظيمي للمستشار الآلي",
            "category": "fintech",
            "summary": "CMA has approved a regulatory framework for robo-advisory services. Firms must be licensed for Managing Investments or Managing Investments and Operating Funds.",
            "summary_ar": "وافقت هيئة السوق المالية على إطار تنظيمي لخدمات المستشار الآلي. يجب أن تكون الشركات مرخصة لإدارة الاستثمارات أو إدارة الاستثمارات وتشغيل الصناديق.",
            "key_requirements": [
                "License for Managing Investments required",
                "IT Officer registration with CMA",
                "Fair and clear algorithm disclosures",
                "Portfolio diversification requirements",
                "Algorithmic oversight and periodic testing",
                "Advance CMA notification for strategy changes",
            ],
            "key_requirements_ar": [
                "ترخيص إدارة الاستثمارات مطلوب",
                "تسجيل مسؤول تقنية المعلومات لدى الهيئة",
                "إفصاحات عادلة وواضحة عن الخوارزميات",
                "متطلبات تنويع المحافظ",
                "الرقابة على الخوارزميات والاختبار الدوري",
                "إخطار الهيئة مسبقاً بتغييرات الاستراتيجية",
            ],
            "reference_url": "https://cma.org.sa/en/RulesRegulations/Regulations/Pages/default.aspx",
        },
        {
            "id": "CMA-INV-001",
            "title": "Investment Account Instructions",
            "title_ar": "تعليمات حسابات الاستثمار",
            "category": "accounts",
            "summary": "Detailed instructions for opening, operating, and supervising investment accounts in the Saudi capital market.",
            "summary_ar": "تعليمات تفصيلية لفتح وتشغيل والإشراف على حسابات الاستثمار في السوق المالية السعودية.",
            "key_requirements": [
                "Client acceptance and KYC verification",
                "Investment account opening agreement",
                "Electronic record maintenance",
                "Regular account information updates",
                "Account freezing procedures for sanctions compliance",
                "Disclosure of account information to authorities",
            ],
            "key_requirements_ar": [
                "قبول العميل والتحقق من معرفة العميل",
                "اتفاقية فتح حساب الاستثمار",
                "الاحتفاظ بالسجلات الإلكترونية",
                "تحديث معلومات الحساب بشكل دوري",
                "إجراءات تجميد الحساب للالتزام بالعقوبات",
                "الإفصاح عن معلومات الحساب للسلطات",
            ],
            "reference_url": "https://cma.gov.sa/en/RulesRegulations/Regulations/Documents/Investment_Accounts_Instructions_EN_V12025.pdf",
        },
    ],
}

# Topic keyword mapping for intelligent query matching
TOPIC_KEYWORDS = {
    "aml": ["aml", "money laundering", "غسل الأموال", "مكافحة غسل", "anti-money", "laundering"],
    "ctf": ["ctf", "terrorism", "terrorist", "financing terrorism", "إرهاب", "تمويل الإرهاب", "terror"],
    "kyc": ["kyc", "cdd", "due diligence", "customer", "identity", "verification", "العناية الواجبة", "هوية", "عميل", "know your customer"],
    "reporting": ["str", "suspicious", "report", "safiu", "sar", "الإبلاغ", "مشبوهة", "تقرير"],
    "fintech": ["fintech", "sandbox", "expermit", "digital", "robo", "تقنية مالية", "FinTech", "technology"],
    "licensing": ["license", "authorization", "permit", "ترخيص", "تصريح", "capital market institution"],
    "data_protection": ["pdpl", "data protection", "privacy", "personal data", "حماية البيانات", "خصوصية"],
    "accounts": ["account", "investment account", "حساب", "حساب استثمار"],
}


class ComplianceKnowledgeService:
    """Service for querying SAMA and CMA regulatory knowledge."""

    @staticmethod
    def search_regulations(
        query: str,
        source: str = "all",  # "sama", "cma", or "all"
        language: str = "en",
        category: Optional[str] = None,
    ) -> list[dict]:
        """Search regulations by query text and optional category filter."""
        results = []
        query_lower = query.lower()

        # Determine which knowledge bases to search
        sources = []
        if source in ("all", "sama"):
            sources.append(("SAMA", SAMA_KNOWLEDGE_BASE))
        if source in ("all", "cma"):
            sources.append(("CMA", CMA_KNOWLEDGE_BASE))

        for source_name, kb in sources:
            for reg in kb["regulations"]:
                # Category filter
                if category and reg["category"] != category:
                    continue

                # Calculate relevance score
                score = 0.0

                # Check title match
                title = reg["title"].lower()
                title_ar = reg.get("title_ar", "")
                if query_lower in title or query_lower in title_ar:
                    score += 0.5

                # Check summary match
                summary = reg["summary"].lower()
                summary_ar = reg.get("summary_ar", "")
                if query_lower in summary or query_lower in summary_ar:
                    score += 0.3

                # Check keyword/topic matching
                matched_topics = set()
                for topic, keywords in TOPIC_KEYWORDS.items():
                    for kw in keywords:
                        if kw.lower() in query_lower:
                            matched_topics.add(topic)

                if reg["category"] in matched_topics:
                    score += 0.4

                # Token overlap for partial matching
                q_tokens = set(query_lower.split())
                title_tokens = set(title.split())
                overlap = len(q_tokens & title_tokens)
                if overlap > 0:
                    score += overlap * 0.1

                # Check requirements for keyword matches
                reqs = reg.get("key_requirements", [])
                reqs_ar = reg.get("key_requirements_ar", [])
                for req in reqs + reqs_ar:
                    if any(qt in req.lower() for qt in q_tokens if len(qt) > 2):
                        score += 0.1
                        break

                if score > 0:
                    # Build result based on language
                    result = {
                        "id": reg["id"],
                        "source": source_name,
                        "source_meta": kb["meta"],
                        "title": reg["title_ar"] if language == "ar" else reg["title"],
                        "category": reg["category"],
                        "summary": reg["summary_ar"] if language == "ar" else reg["summary"],
                        "key_requirements": reg.get("key_requirements_ar" if language == "ar" else "key_requirements", []),
                        "penalties": reg.get("penalties"),
                        "reference_url": reg.get("reference_url"),
                        "relevance_score": round(min(score, 1.0), 2),
                    }
                    results.append(result)

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results

    @staticmethod
    def answer_inquiry(
        question: str,
        source: str = "all",
        language: str = "en",
    ) -> dict:
        """Answer a compliance inquiry using the knowledge base.

        Returns a structured response with relevant regulations and guidance.
        """
        # Search for relevant regulations
        regulations = ComplianceKnowledgeService.search_regulations(
            question, source=source, language=language
        )

        if not regulations:
            return {
                "answer": (
                    "لم يتم العثور على لوائح مطابقة لاستفسارك. يرجى تحسين سؤالك أو التواصل مع الجهة التنظيمية مباشرة."
                    if language == "ar"
                    else "No matching regulations found for your inquiry. Please refine your question or contact the regulatory authority directly."
                ),
                "regulations": [],
                "sources": [],
                "disclaimer": (
                    "هذا الرد مبني على قاعدة المعرفة التنظيمية ولا يشكل مشورة قانونية. يرجى الرجوع إلى المصادر الرسمية."
                    if language == "ar"
                    else "This response is based on the regulatory knowledge base and does not constitute legal advice. Please refer to official sources."
                ),
            }

        # Build structured answer from top matching regulations
        top_regs = regulations[:5]

        # Compose answer
        if language == "ar":
            answer_parts = ["بناءً على اللوائح التنظيمية ذات الصلة:"]
            for i, reg in enumerate(top_regs, 1):
                answer_parts.append(f"\n{i}. **{reg['title']}** ({reg['source']})")
                answer_parts.append(f"   {reg['summary']}")
                if reg["key_requirements"]:
                    answer_parts.append("   المتطلبات الرئيسية:")
                    for req in reg["key_requirements"][:3]:
                        answer_parts.append(f"   • {req}")
        else:
            answer_parts = ["Based on relevant regulatory requirements:"]
            for i, reg in enumerate(top_regs, 1):
                answer_parts.append(f"\n{i}. **{reg['title']}** ({reg['source']})")
                answer_parts.append(f"   {reg['summary']}")
                if reg["key_requirements"]:
                    answer_parts.append("   Key requirements:")
                    for req in reg["key_requirements"][:3]:
                        answer_parts.append(f"   - {req}")

        sources = []
        for reg in top_regs:
            src = {
                "name": reg["source"],
                "regulation": reg["title"],
                "url": reg.get("reference_url"),
            }
            if src not in sources:
                sources.append(src)

        return {
            "answer": "\n".join(answer_parts),
            "regulations": top_regs,
            "sources": sources,
            "disclaimer": (
                "هذا الرد مبني على قاعدة المعرفة التنظيمية ولا يشكل مشورة قانونية. يرجى الرجوع إلى المصادر الرسمية."
                if language == "ar"
                else "This response is based on the regulatory knowledge base and does not constitute legal advice. Please refer to official sources."
            ),
        }

    @staticmethod
    def get_all_regulations(
        source: str = "all",
        language: str = "en",
        category: Optional[str] = None,
    ) -> dict:
        """Get all regulations organized by source."""
        result = {"sama": [], "cma": []}

        if source in ("all", "sama"):
            for reg in SAMA_KNOWLEDGE_BASE["regulations"]:
                if category and reg["category"] != category:
                    continue
                result["sama"].append({
                    "id": reg["id"],
                    "title": reg["title_ar"] if language == "ar" else reg["title"],
                    "category": reg["category"],
                    "summary": reg["summary_ar"] if language == "ar" else reg["summary"],
                    "key_requirements": reg.get("key_requirements_ar" if language == "ar" else "key_requirements", []),
                    "reference_url": reg.get("reference_url"),
                })

        if source in ("all", "cma"):
            for reg in CMA_KNOWLEDGE_BASE["regulations"]:
                if category and reg["category"] != category:
                    continue
                result["cma"].append({
                    "id": reg["id"],
                    "title": reg["title_ar"] if language == "ar" else reg["title"],
                    "category": reg["category"],
                    "summary": reg["summary_ar"] if language == "ar" else reg["summary"],
                    "key_requirements": reg.get("key_requirements_ar" if language == "ar" else "key_requirements", []),
                    "reference_url": reg.get("reference_url"),
                })

        return {
            "sama": {
                "meta": SAMA_KNOWLEDGE_BASE["meta"],
                "regulations": result["sama"],
            },
            "cma": {
                "meta": CMA_KNOWLEDGE_BASE["meta"],
                "regulations": result["cma"],
            },
        }

    @staticmethod
    def get_categories() -> list[dict]:
        """Get all available regulatory categories."""
        return [
            {"id": "aml", "name": "Anti-Money Laundering", "name_ar": "مكافحة غسل الأموال"},
            {"id": "ctf", "name": "Counter-Terrorism Financing", "name_ar": "مكافحة تمويل الإرهاب"},
            {"id": "kyc", "name": "Customer Due Diligence / KYC", "name_ar": "العناية الواجبة / اعرف عميلك"},
            {"id": "reporting", "name": "Suspicious Transaction Reporting", "name_ar": "الإبلاغ عن المعاملات المشبوهة"},
            {"id": "fintech", "name": "FinTech Regulations", "name_ar": "لوائح التقنية المالية"},
            {"id": "licensing", "name": "Licensing & Authorization", "name_ar": "الترخيص والتصريح"},
            {"id": "data_protection", "name": "Data Protection (PDPL)", "name_ar": "حماية البيانات الشخصية"},
            {"id": "accounts", "name": "Investment Accounts", "name_ar": "حسابات الاستثمار"},
        ]
