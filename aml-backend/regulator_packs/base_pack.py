"""Base Regulator Pack - common interface for all regulator packs.

Each regulator pack defines:
- jurisdiction: country/region info
- regulator: regulatory body info
- sources: catalog of monitored regulatory sources
- topics: relevant regulatory topics
- crawler_config: how to fetch content
- parser_config: how to parse content
"""
from dataclasses import dataclass, field


@dataclass
class JurisdictionDef:
    """Jurisdiction definition."""
    name: str
    code: str  # ISO 3166
    name_ar: str = ""
    region: str = ""


@dataclass
class RegulatorDef:
    """Regulator definition."""
    name: str
    abbreviation: str
    name_ar: str = ""
    website: str = ""
    source_url: str = ""
    regulator_type: str = "financial"
    description: str = ""
    description_ar: str = ""


@dataclass
class SourceDef:
    """Source definition for the registry."""
    title: str
    url: str = ""
    source_type: str = "regulation"  # law, regulation, rulebook, circular, guidance, faq
    authority_level: str = "tier_1"  # tier_1, tier_2, tier_3, tier_4
    language: str = "en"
    crawl_frequency: str = "weekly"  # hourly, daily, weekly, monthly, manual
    title_ar: str = ""
    crawler_config: dict = field(default_factory=dict)
    parser_config: dict = field(default_factory=dict)


@dataclass
class TopicDef:
    """Topic definition for classification."""
    name: str
    category: str  # aml, ctf, kyc, sanctions, pep, reporting, governance, fintech, licensing
    name_ar: str = ""
    description: str = ""


@dataclass
class ProvisionFixture:
    """Sample provision for seed data."""
    section_number: str
    title: str
    text: str
    provision_type: str = "article"
    title_ar: str = ""
    text_ar: str = ""


@dataclass
class RegulatorPack:
    """Complete regulator pack definition."""
    pack_id: str
    jurisdiction: JurisdictionDef
    regulator: RegulatorDef
    sources: list[SourceDef] = field(default_factory=list)
    topics: list[TopicDef] = field(default_factory=list)
    sample_provisions: list[ProvisionFixture] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Validate pack completeness. Returns list of issues."""
        issues = []
        if not self.jurisdiction.code:
            issues.append("Missing jurisdiction code")
        if not self.regulator.abbreviation:
            issues.append("Missing regulator abbreviation")
        if not self.sources:
            issues.append("No sources defined")
        for src in self.sources:
            if not src.title:
                issues.append(f"Source missing title: {src}")
            if src.authority_level not in ("tier_1", "tier_2", "tier_3", "tier_4"):
                issues.append(f"Invalid authority level: {src.authority_level}")
        return issues
