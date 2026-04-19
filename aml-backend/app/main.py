from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db, async_session
from app.core.auth import get_password_hash
from app.models.user import User, UserRole, Organization
from app.models.base import generate_uuid
from app.core.config import settings
from sqlalchemy import select


async def seed_default_data():
    """Seed default organization and admin user."""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL))
        if result.scalar_one_or_none():
            return

        org = Organization(
            id=generate_uuid(),
            name="Default Organization",
            name_ar="المنظمة الافتراضية",
            org_type="fintech",
            country="SA",
        )
        db.add(org)
        await db.flush()

        admin = User(
            id=generate_uuid(),
            email=settings.DEFAULT_ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            organization_id=org.id,
        )
        db.add(admin)

        officer = User(
            id=generate_uuid(),
            email="officer@aml-os.sa",
            hashed_password=get_password_hash("officer123"),
            full_name="Sarah Al-Rashid",
            role=UserRole.COMPLIANCE_OFFICER,
            organization_id=org.id,
            preferred_language="ar",
        )
        db.add(officer)

        analyst = User(
            id=generate_uuid(),
            email="analyst@aml-os.sa",
            hashed_password=get_password_hash("analyst123"),
            full_name="Ahmed Al-Dosari",
            role=UserRole.ANALYST,
            organization_id=org.id,
        )
        db.add(analyst)

        auditor = User(
            id=generate_uuid(),
            email="auditor@aml-os.sa",
            hashed_password=get_password_hash("auditor123"),
            full_name="Fatima Al-Zahrani",
            role=UserRole.AUDITOR,
            organization_id=org.id,
        )
        db.add(auditor)

        await db.commit()


async def seed_regulatory_data():
    """Seed regulator pack data (jurisdictions, regulators, sources, topics, provisions)."""
    from app.services.regulatory.seed_service import SeedService
    async with async_session() as db:
        try:
            result = await SeedService.seed_all_packs(db)
            await db.commit()
            if result["packs_loaded"] > 0:
                import logging
                logging.getLogger(__name__).info(f"Seeded regulatory data: {result}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to seed regulatory data: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F811 - imports all models to register with SQLAlchemy
    import app.models.regulatory  # noqa: F811 - register regulatory models
    await init_db()
    await seed_default_data()
    await seed_regulatory_data()
    yield


app = FastAPI(
    title="AML Compliance OS",
    description="Anti-Money Laundering & Compliance Operating System for Saudi Arabia",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

from app.routers import auth, onboarding, screening, risk, transactions, cases, audit, loops, compliance, regulatory
from app.routers import regulatory_phase2
from app.routers import intelligence

app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(screening.router)
app.include_router(risk.router)
app.include_router(transactions.router)
app.include_router(cases.router)
app.include_router(audit.router)
app.include_router(loops.router)
app.include_router(compliance.router)
app.include_router(regulatory.router)
app.include_router(regulatory_phase2.router)
app.include_router(intelligence.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
