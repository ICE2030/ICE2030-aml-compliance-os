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
    # Phase 4: control provenance
    "ALTER TABLE controls ADD COLUMN regulator_id VARCHAR(36)",
    "ALTER TABLE controls ADD COLUMN source_id VARCHAR(36)",
    "ALTER TABLE controls ADD COLUMN seed_key VARCHAR(200)",
    # Phase 4: evidence seed_key
    "ALTER TABLE evidence_artifacts ADD COLUMN seed_key VARCHAR(200)",
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
