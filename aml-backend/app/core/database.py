import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Lightweight schema migrations for SQLite (which doesn't support full ALTER TABLE).
# Each entry is an ALTER TABLE statement that adds a column.  If the column already
# exists, the OperationalError is silently ignored — making this idempotent.
_MIGRATIONS: list[str] = [
    "ALTER TABLE regulatory_sources ADD COLUMN pack_id VARCHAR(100)",
    "ALTER TABLE regulatory_sources ADD COLUMN seed_key VARCHAR(200)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_regulatory_sources_seed_key ON regulatory_sources(seed_key)",
    # Phase 4: obligations.criticality for risk scoring
    "ALTER TABLE obligations ADD COLUMN criticality VARCHAR(50)",
    # Phase 5A: obligation extraction improvements
    "ALTER TABLE obligations ADD COLUMN applies_to_entity_types JSON",
    "ALTER TABLE obligations ADD COLUMN applies_to_product_types JSON",
    "ALTER TABLE obligations ADD COLUMN condition TEXT",
    "ALTER TABLE obligations ADD COLUMN deadline VARCHAR(200)",
    # Phase 4: controls table columns (may be missing if table was created before Phase 4)
    "ALTER TABLE controls ADD COLUMN name_ar VARCHAR(300)",
    "ALTER TABLE controls ADD COLUMN description TEXT",
    "ALTER TABLE controls ADD COLUMN description_ar TEXT",
    "ALTER TABLE controls ADD COLUMN frequency VARCHAR(100)",
    "ALTER TABLE controls ADD COLUMN effectiveness_rating FLOAT",
    "ALTER TABLE controls ADD COLUMN last_tested DATETIME",
    "ALTER TABLE controls ADD COLUMN test_frequency VARCHAR(50)",
    "ALTER TABLE controls ADD COLUMN regulator_id VARCHAR(36)",
    "ALTER TABLE controls ADD COLUMN source_id VARCHAR(36)",
    "ALTER TABLE controls ADD COLUMN seed_key VARCHAR(200)",
    # Phase 4: evidence_artifacts columns
    "ALTER TABLE evidence_artifacts ADD COLUMN name VARCHAR(300)",
    "ALTER TABLE evidence_artifacts ADD COLUMN name_ar VARCHAR(300)",
    "ALTER TABLE evidence_artifacts ADD COLUMN description_ar TEXT",
    "ALTER TABLE evidence_artifacts ADD COLUMN source_system VARCHAR(200)",
    "ALTER TABLE evidence_artifacts ADD COLUMN collection_method VARCHAR(100)",
    "ALTER TABLE evidence_artifacts ADD COLUMN periodicity VARCHAR(100)",
    "ALTER TABLE evidence_artifacts ADD COLUMN owner VARCHAR(200)",
    "ALTER TABLE evidence_artifacts ADD COLUMN file_path VARCHAR(1000)",
    "ALTER TABLE evidence_artifacts ADD COLUMN collected_at DATETIME",
    "ALTER TABLE evidence_artifacts ADD COLUMN expires_at DATETIME",
    "ALTER TABLE evidence_artifacts ADD COLUMN seed_key VARCHAR(200)",
    # Phase 4: regulatory_risks columns
    "ALTER TABLE regulatory_risks ADD COLUMN description_ar TEXT",
    "ALTER TABLE regulatory_risks ADD COLUMN risk_score FLOAT",
    "ALTER TABLE regulatory_risks ADD COLUMN mitigation_status VARCHAR(50)",
    "ALTER TABLE regulatory_risks ADD COLUMN penalty_description TEXT",
    "ALTER TABLE regulatory_risks ADD COLUMN risk_factors JSON",
    # Phase 4: regulatory_actions columns
    "ALTER TABLE regulatory_actions ADD COLUMN deadline DATETIME",
    "ALTER TABLE regulatory_actions ADD COLUMN assigned_to VARCHAR(200)",
    "ALTER TABLE regulatory_actions ADD COLUMN completed_at DATETIME",
    "ALTER TABLE regulatory_actions ADD COLUMN notes TEXT",
    # Phase 4: obligation_controls columns
    "ALTER TABLE obligation_controls ADD COLUMN mapping_confidence FLOAT",
    "ALTER TABLE obligation_controls ADD COLUMN mapping_method VARCHAR(50)",
    "ALTER TABLE obligation_controls ADD COLUMN notes TEXT",
]


async def _run_migrations(conn) -> None:
    """Apply pending column-add migrations (idempotent)."""
    for stmt in _MIGRATIONS:
        try:
            await conn.execute(text(stmt))
            logger.info(f"Migration applied: {stmt}")
        except Exception:
            # Column already exists — safe to ignore
            pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)
