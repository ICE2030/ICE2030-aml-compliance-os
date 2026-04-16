"""Pack Loader - loads and validates all regulator packs."""
import logging
from typing import Optional
from regulator_packs.base_pack import RegulatorPack

logger = logging.getLogger(__name__)

# Registry of available packs
AVAILABLE_PACKS = {
    "fatf": "regulator_packs.fatf",
    "saudi_aml": "regulator_packs.saudi_aml",
    "sama": "regulator_packs.sama",
    "cma": "regulator_packs.cma",
    "insurance_authority": "regulator_packs.insurance_authority",
}


def load_pack(pack_id: str) -> Optional[RegulatorPack]:
    """Load a single regulator pack by ID."""
    if pack_id not in AVAILABLE_PACKS:
        logger.warning(f"Unknown pack: {pack_id}")
        return None
    try:
        import importlib
        module = importlib.import_module(AVAILABLE_PACKS[pack_id])
        pack = module.get_pack()
        issues = pack.validate()
        if issues:
            logger.warning(f"Pack {pack_id} validation issues: {issues}")
        return pack
    except Exception as e:
        logger.error(f"Failed to load pack {pack_id}: {e}")
        return None


def load_all_packs() -> list[RegulatorPack]:
    """Load all available regulator packs."""
    packs = []
    for pack_id in AVAILABLE_PACKS:
        pack = load_pack(pack_id)
        if pack:
            packs.append(pack)
    return packs


def list_packs() -> list[dict]:
    """List all available packs with metadata."""
    result = []
    for pack_id, module_path in AVAILABLE_PACKS.items():
        pack = load_pack(pack_id)
        if pack:
            result.append({
                "pack_id": pack.pack_id,
                "regulator": pack.regulator.name,
                "regulator_ar": pack.regulator.name_ar,
                "abbreviation": pack.regulator.abbreviation,
                "jurisdiction": pack.jurisdiction.name,
                "jurisdiction_code": pack.jurisdiction.code,
                "sources_count": len(pack.sources),
                "topics_count": len(pack.topics),
                "provisions_count": len(pack.sample_provisions),
                "issues": pack.validate(),
            })
    return result
