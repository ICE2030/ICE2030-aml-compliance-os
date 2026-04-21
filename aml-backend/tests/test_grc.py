"""Comprehensive tests for Phase G1 — GRC Expansion Layer.

Tests enterprise risk register, issue management, remediation tracking,
and GRC dashboard endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport

# Import models BEFORE importing app so SQLAlchemy registers them for create_all
import app.models  # noqa: F401
import app.models.regulatory  # noqa: F401
import app.models.grc  # noqa: F401

from app.core.database import init_db
from app.main import app, seed_default_data

BASE = "http://test"

_db_ready = False


@pytest.fixture
async def client():
    global _db_ready
    if not _db_ready:
        await init_db()
        await seed_default_data()
        _db_ready = True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "email": "admin@aml-os.sa",
        "password": "admin123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Enterprise Risk Register ──

@pytest.mark.anyio
async def test_risk_crud(client: AsyncClient, auth_headers: dict):
    """Test create, read, update, delete for enterprise risks."""
    # Create
    resp = await client.post("/api/grc/risks", json={
        "title": "Regulatory Non-Compliance Risk",
        "title_ar": "مخاطر عدم الامتثال التنظيمي",
        "description": "Risk of failing to meet SAMA AML requirements",
        "category": "regulatory",
        "inherent_likelihood": "likely",
        "inherent_impact": "major",
        "residual_likelihood": "possible",
        "residual_impact": "moderate",
        "treatment_strategy": "mitigate",
        "owner": "Chief Compliance Officer",
        "business_unit": "Compliance",
    }, headers=auth_headers)
    assert resp.status_code == 200
    risk = resp.json()
    assert risk["title"] == "Regulatory Non-Compliance Risk"
    assert risk["title_ar"] == "مخاطر عدم الامتثال التنظيمي"
    assert risk["category"] == "regulatory"
    assert risk["inherent_score"] > 0
    assert risk["residual_score"] > 0
    assert risk["inherent_score"] >= risk["residual_score"]
    risk_id = risk["id"]

    # Read single
    resp = await client.get(f"/api/grc/risks/{risk_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == risk_id

    # Update
    resp = await client.put(f"/api/grc/risks/{risk_id}", json={
        "status": "treating",
        "trend_direction": "improving",
        "owner": "Updated CCO",
    }, headers=auth_headers)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "treating"
    assert updated["trend_direction"] == "improving"
    assert updated["owner"] == "Updated CCO"

    # List
    resp = await client.get("/api/grc/risks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    # List with filter
    resp = await client.get("/api/grc/risks?category=regulatory", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Delete
    resp = await client.delete(f"/api/grc/risks/{risk_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == risk_id


@pytest.mark.anyio
async def test_risk_scoring(client: AsyncClient, auth_headers: dict):
    """Test that risk scores are computed correctly (0-1 normalized)."""
    # Create risk with max scores
    resp = await client.post("/api/grc/risks", json={
        "title": "Maximum Scoring Test",
        "description": "Testing score computation",
        "category": "operational",
        "inherent_likelihood": "almost_certain",
        "inherent_impact": "severe",
        "residual_likelihood": "rare",
        "residual_impact": "insignificant",
    }, headers=auth_headers)
    assert resp.status_code == 200
    risk = resp.json()
    # 5*5=25, 25/25=1.0
    assert risk["inherent_score"] == 1.0
    # 1*1=1, 1/25=0.04
    assert risk["residual_score"] == 0.04
    risk_id = risk["id"]

    # Cleanup
    await client.delete(f"/api/grc/risks/{risk_id}", headers=auth_headers)


@pytest.mark.anyio
async def test_risk_summary(client: AsyncClient, auth_headers: dict):
    """Test risk summary endpoint returns proper structure."""
    resp = await client.get("/api/grc/risks/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "high_risks" in data
    assert "by_category" in data
    assert "by_status" in data


@pytest.mark.anyio
async def test_risk_heatmap(client: AsyncClient, auth_headers: dict):
    """Test risk heatmap endpoint returns proper structure."""
    resp = await client.get("/api/grc/risks/heatmap", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "cells" in data
    assert "total_risks" in data


@pytest.mark.anyio
async def test_risk_snapshot(client: AsyncClient, auth_headers: dict):
    """Test risk snapshot capture."""
    # Create a risk first
    resp = await client.post("/api/grc/risks", json={
        "title": "Snapshot Test Risk",
        "description": "For snapshot testing",
        "category": "compliance",
        "inherent_likelihood": "possible",
        "inherent_impact": "moderate",
    }, headers=auth_headers)
    risk_id = resp.json()["id"]

    # Capture snapshot
    resp = await client.post(f"/api/grc/risks/{risk_id}/snapshot", headers=auth_headers)
    assert resp.status_code == 200
    snap = resp.json()
    assert snap["risk_id"] == risk_id
    assert "inherent_score" in snap
    assert "residual_score" in snap

    # Cleanup
    await client.delete(f"/api/grc/risks/{risk_id}", headers=auth_headers)


@pytest.mark.anyio
async def test_risk_categories(client: AsyncClient, auth_headers: dict):
    """Test risk category seeding and listing."""
    # Seed
    resp = await client.post("/api/grc/risks/categories/seed", headers=auth_headers)
    assert resp.status_code == 200

    # List
    resp = await client.get("/api/grc/risks/categories", headers=auth_headers)
    assert resp.status_code == 200
    cats = resp.json()
    assert len(cats) >= 10


# ── Issue Management ──

@pytest.mark.anyio
async def test_issue_crud(client: AsyncClient, auth_headers: dict):
    """Test create, read, update, delete for issues."""
    # Create
    resp = await client.post("/api/grc/issues", json={
        "title": "AML Policy Gap Identified",
        "title_ar": "فجوة في سياسة مكافحة غسل الأموال",
        "description": "Internal audit found gaps in CDD procedures",
        "source": "audit",
        "severity": "high",
        "owner": "Compliance Team Lead",
        "due_date": "2026-06-30T00:00:00",
    }, headers=auth_headers)
    assert resp.status_code == 200
    issue = resp.json()
    assert issue["title"] == "AML Policy Gap Identified"
    assert issue["title_ar"] == "فجوة في سياسة مكافحة غسل الأموال"
    assert issue["source"] == "audit"
    assert issue["severity"] == "high"
    assert issue["status"] == "open"
    assert "aging_days" in issue
    issue_id = issue["id"]

    # Read single
    resp = await client.get(f"/api/grc/issues/{issue_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == issue_id

    # Update
    resp = await client.put(f"/api/grc/issues/{issue_id}", json={
        "status": "in_progress",
        "escalation_status": "escalated_l1",
    }, headers=auth_headers)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "in_progress"
    assert updated["escalation_status"] == "escalated_l1"

    # Close issue
    resp = await client.put(f"/api/grc/issues/{issue_id}", json={
        "status": "closed",
        "closure_evidence": "CDD procedures updated and approved",
    }, headers=auth_headers)
    assert resp.status_code == 200
    closed = resp.json()
    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None

    # List
    resp = await client.get("/api/grc/issues", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    # List with filter
    resp = await client.get("/api/grc/issues?source=audit", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Delete
    resp = await client.delete(f"/api/grc/issues/{issue_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == issue_id


@pytest.mark.anyio
async def test_issue_summary(client: AsyncClient, auth_headers: dict):
    """Test issue summary endpoint."""
    resp = await client.get("/api/grc/issues/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "open" in data
    assert "overdue" in data
    assert "critical_open" in data
    assert "by_source" in data
    assert "by_severity" in data
    assert "by_status" in data


@pytest.mark.anyio
async def test_issue_severity_filter(client: AsyncClient, auth_headers: dict):
    """Test filtering issues by severity."""
    # Create issues with different severities
    for sev in ["low", "critical"]:
        await client.post("/api/grc/issues", json={
            "title": f"Test {sev} issue",
            "description": f"Testing {sev} severity",
            "severity": sev,
        }, headers=auth_headers)

    resp = await client.get("/api/grc/issues?severity=critical", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["severity"] == "critical"


# ── Remediation & Action Tracking ──

@pytest.mark.anyio
async def test_remediation_crud(client: AsyncClient, auth_headers: dict):
    """Test remediation action CRUD with milestones."""
    # First create an issue
    resp = await client.post("/api/grc/issues", json={
        "title": "Remediation Test Issue",
        "description": "Issue to attach remediation actions",
        "source": "compliance",
        "severity": "medium",
    }, headers=auth_headers)
    issue_id = resp.json()["id"]

    # Create action
    resp = await client.post("/api/grc/remediation", json={
        "issue_id": issue_id,
        "title": "Update CDD Procedures",
        "title_ar": "تحديث إجراءات العناية الواجبة",
        "description": "Review and update all CDD procedures to align with latest SAMA guidance",
        "owner": "Compliance Team",
        "target_date": "2026-05-15T00:00:00",
    }, headers=auth_headers)
    assert resp.status_code == 200
    action = resp.json()
    assert action["title"] == "Update CDD Procedures"
    assert action["status"] == "not_started"
    assert action["progress_pct"] == 0
    action_id = action["id"]

    # Update action progress
    resp = await client.put(f"/api/grc/remediation/{action_id}", json={
        "status": "in_progress",
        "progress_pct": 50,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["progress_pct"] == 50
    assert resp.json()["status"] == "in_progress"

    # Create milestones
    resp = await client.post(f"/api/grc/remediation/{action_id}/milestones", json={
        "title": "Draft new CDD policy",
        "target_date": "2026-04-30T00:00:00",
    }, headers=auth_headers)
    assert resp.status_code == 200
    m1 = resp.json()
    assert m1["title"] == "Draft new CDD policy"
    assert m1["is_completed"] is False
    m1_id = m1["id"]

    resp = await client.post(f"/api/grc/remediation/{action_id}/milestones", json={
        "title": "Get management approval",
    }, headers=auth_headers)
    assert resp.status_code == 200
    m2_id = resp.json()["id"]

    # List milestones
    resp = await client.get(f"/api/grc/remediation/{action_id}/milestones", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2

    # Complete milestone
    resp = await client.put(f"/api/grc/remediation/milestones/{m1_id}", json={
        "is_completed": True,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_completed"] is True
    assert resp.json()["completed_at"] is not None

    # Complete action
    resp = await client.put(f"/api/grc/remediation/{action_id}", json={
        "status": "completed",
        "progress_pct": 100,
    }, headers=auth_headers)
    assert resp.status_code == 200
    completed = resp.json()
    assert completed["status"] == "completed"
    assert completed["progress_pct"] == 100
    assert completed["completed_at"] is not None

    # List actions
    resp = await client.get("/api/grc/remediation", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # List actions for specific issue
    resp = await client.get(f"/api/grc/remediation?issue_id={issue_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Delete milestone
    resp = await client.delete(f"/api/grc/remediation/milestones/{m2_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Delete action
    resp = await client.delete(f"/api/grc/remediation/{action_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Cleanup issue
    await client.delete(f"/api/grc/issues/{issue_id}", headers=auth_headers)


@pytest.mark.anyio
async def test_remediation_summary(client: AsyncClient, auth_headers: dict):
    """Test remediation summary endpoint."""
    resp = await client.get("/api/grc/remediation/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "in_progress" in data
    assert "completed" in data
    assert "blocked" in data
    assert "overdue" in data
    assert "avg_progress_pct" in data
    assert "by_status" in data


@pytest.mark.anyio
async def test_remediation_invalid_issue(client: AsyncClient, auth_headers: dict):
    """Test creating remediation for non-existent issue."""
    resp = await client.post("/api/grc/remediation", json={
        "issue_id": "nonexistent-id",
        "title": "Test Action",
        "description": "Should fail",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert "error" in resp.json()


# ── GRC Dashboard ──

@pytest.mark.anyio
async def test_grc_dashboard(client: AsyncClient, auth_headers: dict):
    """Test GRC dashboard executive summary."""
    resp = await client.get("/api/grc/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Verify structure
    assert "generated_at" in data
    assert "risk_register" in data
    assert "issues" in data
    assert "remediation" in data
    assert "regulatory_backbone" in data
    assert "exposure_areas" in data
    assert "recommended_actions" in data
    assert "operating_chain" in data

    # Verify operating chain is present
    assert "Source" in data["operating_chain"]
    assert "Obligation" in data["operating_chain"]
    assert "Risk" in data["operating_chain"]
    assert "Remediation" in data["operating_chain"]

    # Verify risk register section
    rr = data["risk_register"]
    assert "total" in rr
    assert "high_risks" in rr
    assert "deteriorating" in rr

    # Verify issues section
    issues = data["issues"]
    assert "total" in issues
    assert "open" in issues
    assert "critical_open" in issues
    assert "overdue" in issues

    # Verify remediation section
    rem = data["remediation"]
    assert "total" in rem
    assert "blocked" in rem
    assert "overdue" in rem
    assert "avg_progress_pct" in rem

    # Verify regulatory backbone
    rb = data["regulatory_backbone"]
    assert "obligations" in rb
    assert "controls" in rb
    assert "evidence" in rb


@pytest.mark.anyio
async def test_grc_dashboard_recommended_actions(client: AsyncClient, auth_headers: dict):
    """Test that dashboard produces recommended actions."""
    # Create a critical issue to trigger recommendations
    resp = await client.post("/api/grc/issues", json={
        "title": "Critical Test Issue",
        "description": "Testing recommendations",
        "severity": "critical",
    }, headers=auth_headers)
    issue_id = resp.json()["id"]

    # Check dashboard
    resp = await client.get("/api/grc/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Should have at least one recommended action about critical issues
    has_critical_action = any(
        a["priority"] == "critical" for a in data["recommended_actions"]
    )
    assert has_critical_action

    # Cleanup
    await client.delete(f"/api/grc/issues/{issue_id}", headers=auth_headers)


@pytest.mark.anyio
async def test_grc_end_to_end_flow(client: AsyncClient, auth_headers: dict):
    """Test the full GRC flow: risk → issue → remediation → dashboard."""
    # 1. Create enterprise risk
    resp = await client.post("/api/grc/risks", json={
        "title": "E2E Test: Operational Fraud Risk",
        "description": "End-to-end flow test for GRC chain",
        "category": "fraud",
        "inherent_likelihood": "likely",
        "inherent_impact": "major",
        "residual_likelihood": "possible",
        "residual_impact": "moderate",
        "treatment_strategy": "mitigate",
        "owner": "Risk Manager",
    }, headers=auth_headers)
    assert resp.status_code == 200
    risk = resp.json()
    risk_id = risk["id"]
    assert risk["inherent_score"] > 0
    assert risk["residual_score"] > 0

    # 2. Create issue linked to risk
    resp = await client.post("/api/grc/issues", json={
        "title": "E2E Test: Fraud Controls Deficiency",
        "description": "Audit finding: fraud detection controls insufficient",
        "source": "audit",
        "severity": "high",
        "risk_id": risk_id,
        "owner": "Internal Audit",
    }, headers=auth_headers)
    assert resp.status_code == 200
    issue = resp.json()
    issue_id = issue["id"]
    assert issue["risk_id"] == risk_id

    # 3. Create remediation action
    resp = await client.post("/api/grc/remediation", json={
        "issue_id": issue_id,
        "title": "E2E Test: Implement Enhanced Fraud Detection",
        "description": "Deploy ML-based transaction monitoring",
        "owner": "Technology Team",
        "target_date": "2026-07-01T00:00:00",
    }, headers=auth_headers)
    assert resp.status_code == 200
    action = resp.json()
    action_id = action["id"]
    assert action["issue_id"] == issue_id

    # 4. Add milestones
    resp = await client.post(f"/api/grc/remediation/{action_id}/milestones", json={
        "title": "Vendor selection",
        "target_date": "2026-05-01T00:00:00",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # 5. Progress action
    resp = await client.put(f"/api/grc/remediation/{action_id}", json={
        "status": "in_progress",
        "progress_pct": 30,
    }, headers=auth_headers)
    assert resp.status_code == 200

    # 6. Check dashboard reflects the data
    resp = await client.get("/api/grc/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    dashboard = resp.json()
    assert dashboard["risk_register"]["total"] >= 1
    assert dashboard["issues"]["open"] >= 1
    assert dashboard["remediation"]["total"] >= 1

    # 7. Cleanup
    await client.delete(f"/api/grc/remediation/{action_id}", headers=auth_headers)
    await client.delete(f"/api/grc/issues/{issue_id}", headers=auth_headers)
    await client.delete(f"/api/grc/risks/{risk_id}", headers=auth_headers)


@pytest.mark.anyio
async def test_bilingual_support(client: AsyncClient, auth_headers: dict):
    """Test that bilingual fields (EN + AR) work correctly across all GRC entities."""
    # Risk
    resp = await client.post("/api/grc/risks", json={
        "title": "Bilingual Risk Test",
        "title_ar": "اختبار ثنائي اللغة للمخاطر",
        "description": "English description",
        "description_ar": "وصف بالعربية",
        "category": "compliance",
    }, headers=auth_headers)
    assert resp.status_code == 200
    risk = resp.json()
    assert risk["title_ar"] == "اختبار ثنائي اللغة للمخاطر"
    assert risk["description_ar"] == "وصف بالعربية"
    risk_id = risk["id"]

    # Issue
    resp = await client.post("/api/grc/issues", json={
        "title": "Bilingual Issue Test",
        "title_ar": "اختبار ثنائي اللغة للمشاكل",
        "description": "English issue",
        "description_ar": "مشكلة بالعربية",
        "risk_id": risk_id,
    }, headers=auth_headers)
    assert resp.status_code == 200
    issue = resp.json()
    assert issue["title_ar"] == "اختبار ثنائي اللغة للمشاكل"
    issue_id = issue["id"]

    # Remediation
    resp = await client.post("/api/grc/remediation", json={
        "issue_id": issue_id,
        "title": "Bilingual Action Test",
        "title_ar": "اختبار ثنائي اللغة للإجراء",
        "description": "English action",
        "description_ar": "إجراء بالعربية",
    }, headers=auth_headers)
    assert resp.status_code == 200
    action = resp.json()
    assert action["title_ar"] == "اختبار ثنائي اللغة للإجراء"
    action_id = action["id"]

    # Cleanup
    await client.delete(f"/api/grc/remediation/{action_id}", headers=auth_headers)
    await client.delete(f"/api/grc/issues/{issue_id}", headers=auth_headers)
    await client.delete(f"/api/grc/risks/{risk_id}", headers=auth_headers)
