"""Tests for Phase V — Validation & Usage Support.

Covers:
- PhaseVSeedService idempotency (V1 sample data)
- /api/demo/flows structure (V2 demo flows)
- /api/demo/load-samples end-to-end (V1 + V4 integration)
- /api/usage/* event logging, summary, listing (V4)
"""
import pytest
from httpx import AsyncClient, ASGITransport

import app.models  # noqa: F401
import app.models.regulatory  # noqa: F401
import app.models.grc  # noqa: F401

from app.core.database import init_db, async_session
from app.main import app, seed_default_data, seed_regulatory_data
from app.services.grc.phase_v_seed_service import PhaseVSeedService

BASE = "http://test"
_db_ready = False


@pytest.fixture
async def client():
    global _db_ready
    if not _db_ready:
        await init_db()
        await seed_default_data()
        await seed_regulatory_data()
        _db_ready = True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@aml-os.sa", "password": "admin123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── V2: Demo Flows ──

@pytest.mark.anyio
async def test_demo_flows_structure(client: AsyncClient, auth_headers: dict):
    """All three flows must be present and well-formed."""
    resp = await client.get("/api/demo/flows", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    flows = body.get("flows", [])
    keys = {f["key"] for f in flows}
    assert keys == {"compliance", "risk", "audit"}

    for flow in flows:
        assert flow["title_en"] and flow["title_ar"]
        assert flow["description_en"] and flow["description_ar"]
        assert len(flow["steps"]) >= 3
        for step in flow["steps"]:
            assert step["title_en"] and step["title_ar"]
            assert step["path"].startswith("/")
            assert step["hint_en"] and step["hint_ar"]


# ── V1: Sample data seed idempotency ──

@pytest.mark.anyio
async def test_seed_idempotent():
    """Seeding twice must not duplicate records.

    The fixture DB may have already been seeded by another test (e.g. via
    ``/api/demo/load-samples``) — so we only assert that a *follow-up* run is
    a no-op.  Minimum-scenario assertions are covered by
    :func:`test_seed_creates_minimum_scenarios`.
    """
    async with async_session() as db:
        await PhaseVSeedService.seed_all(db)
        await db.commit()

    async with async_session() as db:
        second = await PhaseVSeedService.seed_all(db)
        await db.commit()

    for key, count in second.items():
        assert count == 0, f"Second seed run created {count} new {key} — not idempotent"


@pytest.mark.anyio
async def test_seed_creates_minimum_scenarios():
    """On a fresh DB, the seed must produce the full SAMA/CMA/IA scenario set."""
    from app.models.grc.enterprise_risk import EnterpriseRisk
    from app.models.grc.issue import Issue, RemediationAction
    from app.models.grc.audit import AuditFinding
    from sqlalchemy import select, func

    async with async_session() as db:
        await PhaseVSeedService.seed_all(db)
        await db.commit()
        risks = (await db.execute(select(func.count()).select_from(EnterpriseRisk))).scalar_one()
        issues = (await db.execute(select(func.count()).select_from(Issue))).scalar_one()
        findings = (await db.execute(select(func.count()).select_from(AuditFinding))).scalar_one()
        remediations = (await db.execute(select(func.count()).select_from(RemediationAction))).scalar_one()

    assert risks >= 5
    assert issues >= 5
    assert findings >= 3
    assert remediations >= 3


@pytest.mark.anyio
async def test_demo_load_samples_endpoint(client: AsyncClient, auth_headers: dict):
    """The admin endpoint should succeed and return counts."""
    resp = await client.post("/api/demo/load-samples", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "stats" in body
    # Safe to re-run.
    resp2 = await client.post("/api/demo/load-samples", headers=auth_headers)
    assert resp2.status_code == 200
    for count in resp2.json()["stats"].values():
        assert count == 0


# ── V4: Usage events ──

@pytest.mark.anyio
async def test_usage_event_record_and_list(client: AsyncClient, auth_headers: dict):
    """An authenticated user can record and then list their events."""
    resp = await client.post(
        "/api/usage/events",
        headers=auth_headers,
        json={
            "event_type": "navigate",
            "path": "/grc/risks",
            "resource_type": "risk_register",
        },
    )
    assert resp.status_code == 200, resp.text
    event = resp.json()
    assert event["event_type"] == "navigate"
    assert event["path"] == "/grc/risks"

    list_resp = await client.get("/api/usage/events?limit=10", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(e["id"] == event["id"] for e in items)


@pytest.mark.anyio
async def test_usage_summary_aggregates(client: AsyncClient, auth_headers: dict):
    """Summary returns aggregate counts for the window."""
    # Ensure at least one event exists.
    await client.post(
        "/api/usage/events",
        headers=auth_headers,
        json={"event_type": "create", "resource_type": "risk", "path": "/grc/risks"},
    )
    resp = await client.get("/api/usage/summary?days=7", headers=auth_headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["window_days"] == 7
    assert summary["total_events"] >= 1
    assert "by_event_type" in summary
    assert "top_paths" in summary


@pytest.mark.anyio
async def test_usage_event_types_advertised(client: AsyncClient, auth_headers: dict):
    """The event-type catalog is exposed for the frontend."""
    resp = await client.get("/api/usage/event-types", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    types = set(body.get("event_types", []))
    assert {"create", "update", "delete", "navigate"}.issubset(types)


@pytest.mark.anyio
async def test_usage_invalid_event_type_downgraded(client: AsyncClient, auth_headers: dict):
    """Unknown event types are remapped to 'other' instead of raising."""
    resp = await client.post(
        "/api/usage/events",
        headers=auth_headers,
        json={"event_type": "totally-made-up", "path": "/x"},
    )
    assert resp.status_code == 200
    assert resp.json()["event_type"] == "other"
