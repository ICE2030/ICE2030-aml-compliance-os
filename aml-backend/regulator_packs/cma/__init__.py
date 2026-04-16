"""CMA Regulator Pack - Capital Market Authority (scaffolded for Phase 2)."""
from regulator_packs.base_pack import (
    RegulatorPack, JurisdictionDef, RegulatorDef, SourceDef, TopicDef,
)


def get_pack() -> RegulatorPack:
    return RegulatorPack(
        pack_id="cma",
        jurisdiction=JurisdictionDef(
            name="Kingdom of Saudi Arabia",
            code="SA",
            name_ar="المملكة العربية السعودية",
            region="Middle East",
        ),
        regulator=RegulatorDef(
            name="Capital Market Authority",
            abbreviation="CMA",
            name_ar="هيئة السوق المالية",
            website="https://cma.org.sa",
            source_url="https://cma.org.sa/en/RulesRegulations",
            regulator_type="capital_markets",
            description="Regulator of the Saudi capital market, securities, and authorized persons",
            description_ar="الجهة التنظيمية للسوق المالية السعودية والأوراق المالية والأشخاص المرخص لهم",
        ),
        sources=[
            SourceDef(
                title="CMA AML/CTF Rules for Authorized Persons",
                title_ar="قواعد مكافحة غسل الأموال وتمويل الإرهاب للأشخاص المرخص لهم",
                url="https://cma.org.sa/en/RulesRegulations/Regulations/Pages/default.aspx",
                source_type="rulebook",
                authority_level="tier_1",
                language="en",
                crawl_frequency="weekly",
            ),
            SourceDef(
                title="CMA Authorized Persons Regulations",
                title_ar="لائحة الأشخاص المرخص لهم",
                url="https://cma.org.sa/en/RulesRegulations/Regulations/Pages/default.aspx",
                source_type="regulation",
                authority_level="tier_1",
                language="en",
                crawl_frequency="weekly",
            ),
        ],
        topics=[
            TopicDef(name="AML for Authorized Persons (CMA)", category="aml", name_ar="مكافحة غسل الأموال للأشخاص المرخص لهم"),
            TopicDef(name="Securities Compliance (CMA)", category="licensing", name_ar="التزام الأوراق المالية"),
            TopicDef(name="Crowdfunding Regulations (CMA)", category="fintech", name_ar="أنظمة التمويل الجماعي"),
        ],
    )
