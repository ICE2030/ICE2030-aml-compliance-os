"""Comprehensive tests for Phase G1 + G2 — GRC Expansion Layer.

Tests enterprise risk register, issue management, remediation tracking,
GRC dashboard, audit plans, audit engagements, control tests,
audit findings, and management responses.
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
    assert resp.status_code == 404
    assert "detail" in resp.json()


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


# ── Phase G2: Audit Plan ──

@pytest.mark.anyio
async def test_audit_plan_crud(client: AsyncClient, auth_headers: dict):
    """Test create, read, update, delete for audit plans."""
    # Create
    resp = await client.post("/api/grc/audit-plans", json={
        "title": "Annual AML Audit 2026",
        "title_ar": "التدقيق السنوي لمكافحة غسل الأموال 2026",
        "description": "Comprehensive review of AML controls",
        "scope_summary": "All AML/CTF controls across retail banking",
        "period_start": "2026-01-01T00:00:00",
        "period_end": "2026-12-31T00:00:00",
        "owner": "Chief Audit Executive",
        "status": "draft",
    }, headers=auth_headers)
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["title"] == "Annual AML Audit 2026"
    assert plan["title_ar"] == "التدقيق السنوي لمكافحة غسل الأموال 2026"
    assert plan["status"] == "draft"
    plan_id = plan["id"]

    # Read single
    resp = await client.get(f"/api/grc/audit-plans/{plan_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == plan_id

    # Update
    resp = await client.put(f"/api/grc/audit-plans/{plan_id}", json={
        "status": "approved",
        "owner": "Updated CAE",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["owner"] == "Updated CAE"

    # List
    resp = await client.get("/api/grc/audit-plans", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    # List with filter
    resp = await client.get("/api/grc/audit-plans?status=approved", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Summary
    resp = await client.get("/api/grc/audit-plans/summary", headers=auth_headers)
    assert resp.status_code == 200
    assert "total" in resp.json()
    assert "by_status" in resp.json()

    # Delete
    resp = await client.delete(f"/api/grc/audit-plans/{plan_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == plan_id


# ── Phase G2: Audit Engagement ──

@pytest.mark.anyio
async def test_audit_engagement_crud(client: AsyncClient, auth_headers: dict):
    """Test create, read, update, delete for audit engagements."""
    # Create plan first
    resp = await client.post("/api/grc/audit-plans", json={
        "title": "Engagement Test Plan",
        "description": "Plan for engagement testing",
    }, headers=auth_headers)
    plan_id = resp.json()["id"]

    # Create engagement
    resp = await client.post("/api/grc/audit-engagements", json={
        "plan_id": plan_id,
        "title": "CDD Process Review",
        "title_ar": "مراجعة عملية العناية الواجبة",
        "scope": "Customer Due Diligence procedures",
        "objectives": "Verify CDD controls are operating effectively",
        "owner": "Senior Auditor",
        "status": "planned",
    }, headers=auth_headers)
    assert resp.status_code == 200
    eng = resp.json()
    assert eng["title"] == "CDD Process Review"
    assert eng["plan_id"] == plan_id
    assert eng["status"] == "planned"
    eng_id = eng["id"]

    # Read single
    resp = await client.get(f"/api/grc/audit-engagements/{eng_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == eng_id

    # Update
    resp = await client.put(f"/api/grc/audit-engagements/{eng_id}", json={
        "status": "fieldwork",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "fieldwork"

    # List
    resp = await client.get("/api/grc/audit-engagements", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # List with plan filter
    resp = await client.get(f"/api/grc/audit-engagements?plan_id={plan_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Summary
    resp = await client.get("/api/grc/audit-engagements/summary", headers=auth_headers)
    assert resp.status_code == 200
    assert "total" in resp.json()

    # Delete
    resp = await client.delete(f"/api/grc/audit-engagements/{eng_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Cleanup
    await client.delete(f"/api/grc/audit-plans/{plan_id}", headers=auth_headers)


# ── Phase G2: Control Test ──

@pytest.mark.anyio
async def test_control_test_crud(client: AsyncClient, auth_headers: dict):
    """Test create, read, update, delete for control tests."""
    # Create plan + engagement
    resp = await client.post("/api/grc/audit-plans", json={
        "title": "Control Test Plan",
    }, headers=auth_headers)
    plan_id = resp.json()["id"]

    resp = await client.post("/api/grc/audit-engagements", json={
        "plan_id": plan_id,
        "title": "Control Test Engagement",
    }, headers=auth_headers)
    eng_id = resp.json()["id"]

    # Create control test
    resp = await client.post(f"/api/grc/control-tests/{eng_id}", json={
        "procedure": "Inspect CDD documentation for 25 sample customers",
        "procedure_ar": "فحص وثائق العناية الواجبة لـ 25 عميل عينة",
        "test_type": "both",
        "tester": "Audit Analyst",
        "design_result": "effective",
        "operating_result": "partially_effective",
        "overall_result": "partially_effective",
        "sample_size": 25,
        "exceptions_found": 3,
    }, headers=auth_headers)
    assert resp.status_code == 200
    ct = resp.json()
    assert ct["procedure"].startswith("Inspect CDD")
    assert ct["test_type"] == "both"
    assert ct["overall_result"] == "partially_effective"
    assert ct["sample_size"] == 25
    assert ct["exceptions_found"] == 3
    ct_id = ct["id"]

    # Read single
    resp = await client.get(f"/api/grc/control-tests/{ct_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == ct_id

    # Update
    resp = await client.put(f"/api/grc/control-tests/{ct_id}", json={
        "overall_result": "ineffective",
        "notes": "Multiple exceptions found",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["overall_result"] == "ineffective"
    assert resp.json()["notes"] == "Multiple exceptions found"

    # List
    resp = await client.get("/api/grc/control-tests", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # List with engagement filter
    resp = await client.get(f"/api/grc/control-tests?engagement_id={eng_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Summary
    resp = await client.get("/api/grc/control-tests/summary", headers=auth_headers)
    assert resp.status_code == 200
    assert "total" in resp.json()
    assert "by_result" in resp.json()

    # Delete
    resp = await client.delete(f"/api/grc/control-tests/{ct_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Cleanup
    await client.delete(f"/api/grc/audit-engagements/{eng_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-plans/{plan_id}", headers=auth_headers)


# ── Phase G2: Audit Finding + Management Response ──

@pytest.mark.anyio
async def test_audit_finding_and_response(client: AsyncClient, auth_headers: dict):
    """Test full finding + management response lifecycle."""
    # Create plan + engagement
    resp = await client.post("/api/grc/audit-plans", json={
        "title": "Finding Test Plan",
    }, headers=auth_headers)
    plan_id = resp.json()["id"]

    resp = await client.post("/api/grc/audit-engagements", json={
        "plan_id": plan_id,
        "title": "Finding Test Engagement",
    }, headers=auth_headers)
    eng_id = resp.json()["id"]

    # Create finding
    resp = await client.post(f"/api/grc/audit-findings/{eng_id}", json={
        "title": "Inadequate CDD Documentation",
        "title_ar": "عدم كفاية وثائق العناية الواجبة",
        "description": "12% of sampled accounts had incomplete CDD files",
        "severity": "high",
        "status": "open",
        "root_cause": "Lack of standardized documentation checklist",
        "owner": "Compliance Manager",
        "due_date": "2026-06-30T00:00:00",
    }, headers=auth_headers)
    assert resp.status_code == 200
    finding = resp.json()
    assert finding["title"] == "Inadequate CDD Documentation"
    assert finding["severity"] == "high"
    assert finding["status"] == "open"
    finding_id = finding["id"]

    # Read single
    resp = await client.get(f"/api/grc/audit-findings/{finding_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == finding_id

    # Update
    resp = await client.put(f"/api/grc/audit-findings/{finding_id}", json={
        "status": "in_remediation",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_remediation"

    # List
    resp = await client.get("/api/grc/audit-findings", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Filter by severity
    resp = await client.get("/api/grc/audit-findings?severity=high", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Summary
    resp = await client.get("/api/grc/audit-findings/summary", headers=auth_headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert "total" in summary
    assert "open" in summary
    assert "by_severity" in summary
    assert "by_status" in summary

    # ── Management Response ──

    # Create response
    resp = await client.post(f"/api/grc/management-responses/{finding_id}", json={
        "response_text": "We will implement a standardized CDD checklist",
        "response_text_ar": "سنقوم بتطبيق قائمة مراجعة موحدة للعناية الواجبة",
        "owner": "Compliance Manager",
        "due_date": "2026-05-15T00:00:00",
        "status": "accepted",
    }, headers=auth_headers)
    assert resp.status_code == 200
    mgmt_resp = resp.json()
    assert mgmt_resp["response_text"].startswith("We will implement")
    assert mgmt_resp["status"] == "accepted"
    resp_id = mgmt_resp["id"]

    # Read single
    resp = await client.get(f"/api/grc/management-responses/{resp_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == resp_id

    # Update
    resp = await client.put(f"/api/grc/management-responses/{resp_id}", json={
        "status": "completed",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["completed_at"] is not None

    # List
    resp = await client.get("/api/grc/management-responses", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # List by finding
    resp = await client.get(f"/api/grc/management-responses?finding_id={finding_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # Close finding
    resp = await client.put(f"/api/grc/audit-findings/{finding_id}", json={
        "status": "closed",
        "closure_evidence": "CDD checklist implemented and trained",
        "closure_validated_by": "Head of Internal Audit",
    }, headers=auth_headers)
    assert resp.status_code == 200
    closed = resp.json()
    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None
    assert closed["closure_validated_by"] == "Head of Internal Audit"

    # Cleanup
    await client.delete(f"/api/grc/management-responses/{resp_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-findings/{finding_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-engagements/{eng_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-plans/{plan_id}", headers=auth_headers)


# ── Phase G2: End-to-End Audit Flow ──

@pytest.mark.anyio
async def test_audit_end_to_end_flow(client: AsyncClient, auth_headers: dict):
    """Test full audit lifecycle: plan → engagement → test → finding → response."""
    # 1. Create audit plan
    resp = await client.post("/api/grc/audit-plans", json={
        "title": "E2E Audit Plan",
        "title_ar": "خطة التدقيق الشاملة",
        "status": "approved",
    }, headers=auth_headers)
    assert resp.status_code == 200
    plan_id = resp.json()["id"]

    # 2. Create engagement under plan
    resp = await client.post("/api/grc/audit-engagements", json={
        "plan_id": plan_id,
        "title": "E2E AML Compliance Engagement",
        "title_ar": "مهمة الامتثال الشاملة",
        "status": "fieldwork",
    }, headers=auth_headers)
    assert resp.status_code == 200
    eng_id = resp.json()["id"]

    # 3. Create control test under engagement
    resp = await client.post(f"/api/grc/control-tests/{eng_id}", json={
        "procedure": "Review transaction monitoring alerts for false positive rates",
        "test_type": "operating",
        "overall_result": "ineffective",
        "sample_size": 50,
        "exceptions_found": 15,
    }, headers=auth_headers)
    assert resp.status_code == 200
    ct_id = resp.json()["id"]

    # 4. Create finding from failed test
    resp = await client.post(f"/api/grc/audit-findings/{eng_id}", json={
        "title": "High False Positive Rate in TM",
        "title_ar": "معدل إنذارات كاذبة مرتفع في مراقبة المعاملات",
        "description": "30% false positive rate exceeds 10% threshold",
        "severity": "critical",
        "status": "open",
        "root_cause": "Outdated detection rules",
    }, headers=auth_headers)
    assert resp.status_code == 200
    finding_id = resp.json()["id"]
    assert resp.json()["severity"] == "critical"

    # 5. Create management response
    resp = await client.post(f"/api/grc/management-responses/{finding_id}", json={
        "response_text": "We will recalibrate TM rules and reduce FP rate to <5%",
        "response_text_ar": "سنعيد معايرة قواعد المراقبة وتقليل معدل الإنذارات الكاذبة إلى أقل من 5%",
        "owner": "Head of Financial Crime",
        "status": "accepted",
    }, headers=auth_headers)
    assert resp.status_code == 200
    resp_id = resp.json()["id"]

    # 6. Verify dashboard includes audit data
    resp = await client.get("/api/grc/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    dashboard = resp.json()
    assert "audit" in dashboard
    audit_section = dashboard["audit"]
    assert audit_section["total_findings"] >= 1
    assert audit_section["open_findings"] >= 1
    assert audit_section["critical_findings"] >= 1

    # Cleanup
    await client.delete(f"/api/grc/management-responses/{resp_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-findings/{finding_id}", headers=auth_headers)
    await client.delete(f"/api/grc/control-tests/{ct_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-engagements/{eng_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-plans/{plan_id}", headers=auth_headers)


@pytest.mark.anyio
async def test_audit_invalid_references(client: AsyncClient, auth_headers: dict):
    """Test error handling for invalid references."""
    # Invalid plan reference for engagement
    resp = await client.post("/api/grc/audit-engagements", json={
        "plan_id": "nonexistent-plan-id",
        "title": "Should Fail",
    }, headers=auth_headers)
    assert resp.status_code == 404

    # Invalid engagement reference for control test
    resp = await client.post("/api/grc/control-tests/nonexistent-eng-id", json={
        "procedure": "Should Fail",
    }, headers=auth_headers)
    assert resp.status_code == 404

    # Invalid engagement reference for finding
    resp = await client.post("/api/grc/audit-findings/nonexistent-eng-id", json={
        "title": "Should Fail",
        "description": "Should Fail",
    }, headers=auth_headers)
    assert resp.status_code == 404

    # Invalid finding reference for response
    resp = await client.post("/api/grc/management-responses/nonexistent-finding-id", json={
        "response_text": "Should Fail",
    }, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_audit_bilingual(client: AsyncClient, auth_headers: dict):
    """Test bilingual support across all audit entities."""
    # Plan
    resp = await client.post("/api/grc/audit-plans", json={
        "title": "Bilingual Audit Plan",
        "title_ar": "خطة تدقيق ثنائية اللغة",
        "description": "English description",
        "description_ar": "وصف بالعربية",
        "scope_summary": "English scope",
        "scope_summary_ar": "نطاق بالعربية",
    }, headers=auth_headers)
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["title_ar"] == "خطة تدقيق ثنائية اللغة"
    assert plan["scope_summary_ar"] == "نطاق بالعربية"
    plan_id = plan["id"]

    # Engagement
    resp = await client.post("/api/grc/audit-engagements", json={
        "plan_id": plan_id,
        "title": "Bilingual Engagement",
        "title_ar": "مهمة تدقيق ثنائية اللغة",
    }, headers=auth_headers)
    assert resp.status_code == 200
    eng = resp.json()
    assert eng["title_ar"] == "مهمة تدقيق ثنائية اللغة"
    eng_id = eng["id"]

    # Control Test
    resp = await client.post(f"/api/grc/control-tests/{eng_id}", json={
        "procedure": "Test procedure in English",
        "procedure_ar": "إجراء الاختبار بالعربية",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["procedure_ar"] == "إجراء الاختبار بالعربية"
    ct_id = resp.json()["id"]

    # Finding
    resp = await client.post(f"/api/grc/audit-findings/{eng_id}", json={
        "title": "Bilingual Finding",
        "title_ar": "نتيجة تدقيق ثنائية اللغة",
        "description": "English finding",
        "description_ar": "نتيجة بالعربية",
    }, headers=auth_headers)
    assert resp.status_code == 200
    finding = resp.json()
    assert finding["title_ar"] == "نتيجة تدقيق ثنائية اللغة"
    finding_id = finding["id"]

    # Response
    resp = await client.post(f"/api/grc/management-responses/{finding_id}", json={
        "response_text": "English response",
        "response_text_ar": "استجابة بالعربية",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["response_text_ar"] == "استجابة بالعربية"
    resp_id = resp.json()["id"]

    # Cleanup
    await client.delete(f"/api/grc/management-responses/{resp_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-findings/{finding_id}", headers=auth_headers)
    await client.delete(f"/api/grc/control-tests/{ct_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-engagements/{eng_id}", headers=auth_headers)
    await client.delete(f"/api/grc/audit-plans/{plan_id}", headers=auth_headers)
