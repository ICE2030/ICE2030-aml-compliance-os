"""Insurance Authority (IA) Regulator Pack — Saudi Arabia.

Comprehensive pack covering all 27 IA regulation documents including:
- AML/CTF regulations
- Corporate governance
- Anti-fraud
- Risk management
- Reinsurance
- Market conduct
- Customer protection
- Investment regulations
- Actuarial controls
- Licensing and supervision
- And more

Source: Official IA regulations Excel reference file.
"""
from regulator_packs.base_pack import (
    RegulatorPack, JurisdictionDef, RegulatorDef, SourceDef, TopicDef,
)


# ── Document definitions: one per Excel sheet ──────────────────────────
# Each maps to a Source in the registry + a RegulatoryDocument with provisions.

IA_DOCUMENTS = [
    {
        "key": "ia_motor_comprehensive",
        "title": "Comprehensive Insurance Regulations (Motor Vehicles)",
        "title_ar": "ضوابط التأمين الشامل (السيارات)",
        "sheet": "ضوابط التأمين الشامل (السيارات)",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Products (IA)", "Motor Insurance (IA)"],
    },
    {
        "key": "ia_reinsurance",
        "title": "Reinsurance Regulation",
        "title_ar": "لائحة إعادة التأمين",
        "sheet": "لائحة إعادة التأمين",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Reinsurance (IA)"],
    },
    {
        "key": "ia_outsourcing",
        "title": "Outsourcing Regulation",
        "title_ar": "لائحة الإسناد",
        "sheet": "لائحة الإسناد",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)"],
    },
    {
        "key": "ia_governance",
        "title": "Corporate Governance Regulation",
        "title_ar": "لائحة الحوكمة",
        "sheet": "لائحة الحوكمة",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)"],
    },
    {
        "key": "ia_market_conduct",
        "title": "Market Conduct Regulation",
        "title_ar": "لائحة سلوكيات السوق",
        "sheet": "لائحة سلوكيات السوق",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)", "Customer Protection (IA)"],
    },
    {
        "key": "ia_electronic_insurance",
        "title": "Electronic Insurance Operations Regulation",
        "title_ar": "لائحة عمليات التأمين الالكتروني",
        "sheet": "لائحة عمليات التأمين الالكتروني",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Fintech (IA)"],
    },
    {
        "key": "ia_audit_committees",
        "title": "Audit Committees Regulation",
        "title_ar": "لائحة لجان المراجعة",
        "sheet": "لائحة لجان المراجعة",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)"],
    },
    {
        "key": "ia_anti_fraud",
        "title": "Anti-Fraud Regulation",
        "title_ar": "لائحة مكافحة الاحتيال",
        "sheet": "لائحة مكافحة الاحتيال",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance AML Compliance (IA)", "Insurance Anti-Fraud (IA)"],
    },
    {
        "key": "ia_customer_protection",
        "title": "Customer Protection Principles for Insurance Companies",
        "title_ar": "مبادئ حماية عملاء شركات التأمين",
        "sheet": "مبادئ حماية عملاء شركات التأمين",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Customer Protection (IA)"],
    },
    {
        "key": "ia_appointment_requirements",
        "title": "Appointment Requirements",
        "title_ar": "متطلبات التعيين",
        "sheet": "متطلبات التعيين",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Licensing (IA)"],
    },
    {
        "key": "ia_supervision_law",
        "title": "Insurance Companies Supervision Law",
        "title_ar": "نظام مراقبة شركات التأمين",
        "sheet": "نظام مراقبة شركات التأمين",
        "source_type": "law",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)", "Insurance Supervision (IA)"],
    },
    {
        "key": "ia_latent_defects",
        "title": "Latent Defects Insurance Policy",
        "title_ar": "وثيقة العيوب الخفية",
        "sheet": "وثيقة العيوب الخفية",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Products (IA)"],
    },
    {
        "key": "ia_govt_vehicle_insurance",
        "title": "Government Vehicle Insurance Policy",
        "title_ar": "وثيقة تأمين المركبات الحكومية",
        "sheet": "وثيقة تأمين المركبات الحكومية",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Products (IA)", "Motor Insurance (IA)"],
    },
    {
        "key": "ia_investment",
        "title": "Investment Regulation",
        "title_ar": "لائحة الاستثمار",
        "sheet": "لائحة الاستثمار- INVESTMENT REG",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)"],
    },
    {
        "key": "ia_surplus_distribution",
        "title": "Insurance Surplus Distribution Policy",
        "title_ar": "سياسة توزيع فائض التأمين",
        "sheet": "سياسة توزيع فائض التأمين",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Products (IA)"],
    },
    {
        "key": "ia_rules_insurance_business",
        "title": "Rules Governing Insurance Business",
        "title_ar": "القواعد المنظمة لأعمال التأمين",
        "sheet": "القواعد المنظمة لأعمال التأمين ",
        "source_type": "rulebook",
        "authority_level": "tier_1",
        "topics": ["Insurance Products (IA)", "Insurance Governance (IA)"],
    },
    {
        "key": "ia_rules_brokerage",
        "title": "Rules Governing Insurance Brokerage Business",
        "title_ar": "القواعد المنظمة لأعمال وساطة التأمين",
        "sheet": "القواعد المنظمة لأعمال وساطة Ee",
        "source_type": "rulebook",
        "authority_level": "tier_1",
        "topics": ["Insurance Licensing (IA)"],
    },
    {
        "key": "ia_supervision_costs",
        "title": "Supervision and Inspection Costs Regulation",
        "title_ar": "لائحة تكاليف الإشراف والتفتيش",
        "sheet": "لائحة تكاليف الإشراف والتفتيش",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Supervision (IA)"],
    },
    {
        "key": "ia_disability_services",
        "title": "Services for Persons with Disabilities",
        "title_ar": "خدمات ذوي الإعاقة",
        "sheet": "خدمات ذوي الإعاقة",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Customer Protection (IA)"],
    },
    {
        "key": "ia_foreign_licensing",
        "title": "Foreign Companies Licensing Rules",
        "title_ar": "قواعد ترخيص الشركات الأجنبية",
        "sheet": "قواعد ترخيص الشركات الأجنبية",
        "source_type": "rulebook",
        "authority_level": "tier_1",
        "topics": ["Insurance Licensing (IA)"],
    },
    {
        "key": "ia_product_approval",
        "title": "Insurance Products Approval Controls",
        "title_ar": "ضوابط اعتماد المنتجات التأمينية",
        "sheet": "ضوابط اعتماد المنتجات التأميني",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Products (IA)"],
    },
    {
        "key": "ia_branch_expansion",
        "title": "Branch Expansion and Points of Sale Controls",
        "title_ar": "ضوابط توسع الفروع ونقاط البيع",
        "sheet": "\u200e\u2068ضوابط توسع الفروع ونقاط البيع",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Licensing (IA)"],
    },
    {
        "key": "ia_risk_management",
        "title": "Risk Management Regulation",
        "title_ar": "لائحة إدارة المخاطر",
        "sheet": "لائحة إدارة المخاطر",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)", "Insurance Risk Management (IA)"],
    },
    {
        "key": "ia_brokers_agents",
        "title": "Regulatory Framework for Insurance Brokers and Agents",
        "title_ar": "اللائحة التنظيمية لوسطاء ووكلاء التأمين",
        "sheet": "اللائحة التنظيمية لوسطاء ووكلاء",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Licensing (IA)"],
    },
    {
        "key": "ia_actuarial_controls",
        "title": "Actuarial Work Controls",
        "title_ar": "ضوابط الأعمال الاكتوارية",
        "sheet": "ضوابط الأعمال الاكتوارية ",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Products (IA)"],
    },
    {
        "key": "ia_implementing_regulations",
        "title": "Implementing Regulations of Insurance Supervision Law",
        "title_ar": "اللائحة التنفيذية لنظام مراقبة شركات التأمين",
        "sheet": " التنفيذية لنظام مراقبة التأمين",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance Governance (IA)", "Insurance Supervision (IA)"],
    },
    {
        "key": "ia_aml_ctf",
        "title": "AML/CTF Regulations",
        "title_ar": "لائحة مكافحة غسل الأموال وتمويل الإرهاب",
        "sheet": "AML&CTF",
        "source_type": "regulation",
        "authority_level": "tier_1",
        "topics": ["Insurance AML Compliance (IA)", "Insurance KYC (IA)", "Insurance Anti-Fraud (IA)"],
    },
]

# ── Topic definitions ──────────────────────────────────────────────────
IA_TOPICS = [
    TopicDef(name="Insurance AML Compliance (IA)", category="aml",
             name_ar="التزام التأمين بمكافحة غسل الأموال",
             description="AML/CTF compliance requirements for insurance sector"),
    TopicDef(name="Insurance KYC (IA)", category="kyc",
             name_ar="اعرف عميلك في التأمين",
             description="Know Your Customer requirements for insurance"),
    TopicDef(name="Insurance Anti-Fraud (IA)", category="aml",
             name_ar="مكافحة الاحتيال في التأمين",
             description="Anti-fraud regulations for insurance companies"),
    TopicDef(name="Insurance Governance (IA)", category="governance",
             name_ar="حوكمة شركات التأمين",
             description="Corporate governance for insurance companies"),
    TopicDef(name="Insurance Products (IA)", category="insurance",
             name_ar="المنتجات التأمينية",
             description="Insurance product regulations and approvals"),
    TopicDef(name="Insurance Licensing (IA)", category="licensing",
             name_ar="ترخيص شركات التأمين",
             description="Licensing and registration of insurance entities"),
    TopicDef(name="Insurance Supervision (IA)", category="governance",
             name_ar="الرقابة على شركات التأمين",
             description="Supervision and inspection of insurance companies"),
    TopicDef(name="Insurance Fintech (IA)", category="fintech",
             name_ar="التأمين الإلكتروني",
             description="Electronic and digital insurance operations"),
    TopicDef(name="Customer Protection (IA)", category="governance",
             name_ar="حماية عملاء التأمين",
             description="Customer protection principles in insurance"),
    TopicDef(name="Reinsurance (IA)", category="insurance",
             name_ar="إعادة التأمين",
             description="Reinsurance regulations"),
    TopicDef(name="Motor Insurance (IA)", category="insurance",
             name_ar="تأمين المركبات",
             description="Motor vehicle insurance regulations"),
    TopicDef(name="Insurance Risk Management (IA)", category="governance",
             name_ar="إدارة المخاطر في التأمين",
             description="Risk management framework for insurance companies"),
]


def get_pack() -> RegulatorPack:
    """Build the full Insurance Authority regulator pack."""
    sources = []
    for doc in IA_DOCUMENTS:
        sources.append(SourceDef(
            title=doc["title"],
            key=doc["key"],
            title_ar=doc["title_ar"],
            url="https://ia.gov.sa/en/Regulations",
            source_type=doc["source_type"],
            authority_level=doc["authority_level"],
            language="ar+en",
            crawl_frequency="monthly",
            topic_names=doc["topics"],
        ))

    return RegulatorPack(
        pack_id="insurance_authority",
        jurisdiction=JurisdictionDef(
            name="Kingdom of Saudi Arabia",
            code="SA",
            name_ar="المملكة العربية السعودية",
            region="Middle East",
        ),
        regulator=RegulatorDef(
            name="Insurance Authority",
            abbreviation="IA",
            name_ar="هيئة التأمين",
            website="https://ia.gov.sa",
            source_url="https://ia.gov.sa/en/Regulations",
            regulator_type="insurance",
            description="Regulator of the Saudi insurance sector — covers all insurance, reinsurance, and insurance-related service providers in the Kingdom",
            description_ar="الجهة التنظيمية لقطاع التأمين في المملكة العربية السعودية — تغطي جميع شركات التأمين وإعادة التأمين ومقدمي الخدمات المتعلقة بالتأمين",
        ),
        sources=sources,
        topics=IA_TOPICS,
    )
