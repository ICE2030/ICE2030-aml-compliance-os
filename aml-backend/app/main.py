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


async def seed_phase4_data():
    """Seed Phase 4 controls, evidence, and obligation mappings."""
    from app.services.regulatory.phase4_seed_service import Phase4SeedService
    async with async_session() as db:
        try:
            result = await Phase4SeedService.seed_all(db)
            await db.commit()
            if result["controls_created"] > 0 or result["risks_scored"] > 0:
                import logging
                logging.getLogger(__name__).info(f"Seeded Phase 4 data: {result}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to seed Phase 4 data: {e}")


async def seed_phase_v_data():
    """Seed Phase V realistic SAMA/CMA/IA GRC scenarios (idempotent)."""
    from app.services.grc.phase_v_seed_service import PhaseVSeedService
    async with async_session() as db:
        try:
            result = await PhaseVSeedService.seed_all(db)
            await db.commit()
            if any(v > 0 for v in result.values()):
                import logging
                logging.getLogger(__name__).info(f"Seeded Phase V sample data: {result}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to seed Phase V data: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F811 - imports all models to register with SQLAlchemy
    import app.models.regulatory  # noqa: F811 - register regulatory models
    import app.models.grc  # noqa: F811 - register GRC models
    await init_db()
    await seed_default_data()
    await seed_regulatory_data()
    await seed_phase4_data()
    await seed_phase_v_data()
    yield


app = FastAPI(
    title="GRC Intelligence OS",
    description="Regulatory Intelligence-Driven GRC Operating System — AML, Compliance, Risk, Issues, Remediation",
    version="2.0.0",
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
from app.routers import phase4
from app.routers import phase5a
from app.routers import phase5b
from app.routers import ia_regulations
from app.routers import phase_r
from app.routers import grc_risks, grc_issues, grc_remediation, grc_dashboard
from app.routers import grc_audit_plans, grc_audit_engagements, grc_control_tests, grc_audit_findings, grc_management_responses
from app.routers import grc_actions, grc_narratives, grc_cross_links
from app.routers import phase_p
from app.routers import demo_flows, usage

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
app.include_router(phase4.router)
app.include_router(phase5a.router)
app.include_router(phase5b.router)
app.include_router(ia_regulations.router)
app.include_router(phase_r.router)
app.include_router(grc_risks.router)
app.include_router(grc_issues.router)
app.include_router(grc_remediation.router)
app.include_router(grc_dashboard.router)
app.include_router(grc_audit_plans.router)
app.include_router(grc_audit_engagements.router)
app.include_router(grc_control_tests.router)
app.include_router(grc_audit_findings.router)
app.include_router(grc_management_responses.router)
app.include_router(grc_actions.router)
app.include_router(grc_narratives.router)
app.include_router(grc_cross_links.router)
app.include_router(phase_p.router)
app.include_router(demo_flows.router)
app.include_router(usage.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
