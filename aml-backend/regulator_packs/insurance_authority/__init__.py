"""Insurance Authority Regulator Pack (scaffolded for Phase 2)."""
from regulator_packs.base_pack import (
    RegulatorPack, JurisdictionDef, RegulatorDef, SourceDef, TopicDef,
)


def get_pack() -> RegulatorPack:
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
            regulator_type="insurance",
            description="Regulator of the Saudi insurance sector",
            description_ar="الجهة التنظيمية لقطاع التأمين في المملكة العربية السعودية",
        ),
        sources=[
            SourceDef(
                title="Insurance Authority AML/CTF Instructions",
                title_ar="تعليمات مكافحة غسل الأموال وتمويل الإرهاب - هيئة التأمين",
                url="https://ia.gov.sa/en/Regulations",
                source_type="regulation",
                authority_level="tier_1",
                language="en",
                crawl_frequency="weekly",
            ),
        ],
        topics=[
            TopicDef(name="Insurance AML Compliance (IA)", category="aml", name_ar="التزام التأمين بمكافحة غسل الأموال"),
            TopicDef(name="Insurance KYC (IA)", category="kyc", name_ar="اعرف عميلك في التأمين"),
        ],
    )
