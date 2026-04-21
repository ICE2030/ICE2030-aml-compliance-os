# Strategic Naming Recommendation

## Current State
- **Repo**: `ICE2030/ICE2030-aml-compliance-os`
- **App Title**: "AML Compliance OS"
- **Sidebar**: "AML-OS"
- **FastAPI Title**: "AML Compliance OS"

## Recommendation: Keep Repo Name, Rebrand Product Internally

### Decision: **Retain repo name for continuity, rebrand product identity to "GRC OS"**

### Rationale

| Factor | Rename Repo | Keep Repo + Rebrand UI/Docs |
|--------|------------|---------------------------|
| **Continuity** | Breaks all PR links, CI configs, deploy URLs | Zero breakage |
| **Migration complexity** | High — GitHub redirect expires, Fly.io redeploy, frontend URLs change | Zero migration |
| **Strategic clarity** | Repo name matches product | Repo name is legacy, product name is current |
| **Current traction** | 7 merged PRs, deployed backend/frontend, seeded data | All preserved |
| **Product breadth** | Visible in repo name | Visible in UI, docs, API title |

### What Changes Now (Phase G1)

1. **FastAPI app title**: "AML Compliance OS" → "GRC Intelligence OS"
2. **FastAPI description**: Updated to reflect full GRC scope
3. **Sidebar brand**: "AML-OS" → "GRC-OS"
4. **App subtitle**: Updated bilingual
5. **Docs**: architecture.md, roadmap.md updated to reflect GRC positioning
6. **Login page**: Reflects broader platform identity

### What Does NOT Change Now

- Repo name (`ICE2030/ICE2030-aml-compliance-os`) — defer until v2.0 milestone
- Deployed URLs (Fly.io, frontend)
- Database schema naming
- Existing API endpoint paths

### Future Rename Plan (When Ready)

If repo rename is desired later:
1. Create new repo `ICE2030/grc-os` (or `grc-intelligence-os`)
2. Push all branches
3. Update Fly.io app name
4. Redeploy frontend with new API URL
5. Archive old repo with redirect notice
6. Estimated effort: ~2 hours, zero downtime with proper sequencing

---

## Phased Delivery Plan

### Phase G1 (Current)
- Strategic naming recommendation
- Enterprise Risk Register (full CRUD + risk scoring)
- Issue Management (CRUD + lifecycle)
- Remediation & Action Tracking (milestones, progress)
- GRC Dashboard Executive Summary (command center)
- Internal product rebranding (UI/docs)

### Phase G2 (Next)
- Internal Audit module (AuditPlan, AuditEngagement, AuditFinding)
- Control Testing & Assurance lifecycle
- Management Response tracking
- Dashboard audit layer integration

### Phase G3 (After G2)
- Alerting improvements & Action Center
- Deep cross-linking (risk→audit→finding→issue→remediation)
- Narrative summaries (AI-assisted)
- Dashboard drilldowns
- Hardening & performance optimization
