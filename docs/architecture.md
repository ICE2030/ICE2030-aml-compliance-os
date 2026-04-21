# AML Compliance OS - Architecture

## System Vision

AML Compliance OS is a Saudi-first, globally aware **Regulatory Intelligence and Compliance Operating System**. It is not just a search engine or chatbot — it is a self-improving system that collects, parses, structures, and reasons about regulatory knowledge.

## Core Architecture Chain

```
Source → Provision → Obligation → Control → Evidence → Risk → Action
```

For every regulatory statement, the system answers:
- **What is the source?** (jurisdiction, regulator, binding status)
- **What provision says it?** (exact text, section reference)
- **What obligation arises?** (mandatory action, prohibition, deadline)
- **To whom does it apply?** (entity type, product type, jurisdiction)
- **What control satisfies it?** (policy, procedure, workflow)
- **What evidence proves compliance?** (artifact, attestation, log)
- **What risk exists if not met?** (penalty, enforcement, reputational)
- **What action should be taken?** (remediation, review, filing)

## System Thinking Model

```
Players → Interactions → Loops → Patterns → Outcomes
```

### Players
| Player | Role |
|--------|------|
| Regulators | Publish rules, guidance, enforcement |
| Regulated Entities | Must comply, report, evidence |
| Compliance Officers | Interpret, implement, monitor |
| Analysts | Investigate cases, screen entities |
| Auditors | Verify controls, trace evidence |
| AI Agents | Parse, extract, suggest, detect changes |
| Control Owners | Implement and maintain controls |

### Interactions
- **publish** → regulator issues new regulation
- **ingest** → system crawls and parses source
- **parse** → structure raw content into provisions
- **extract** → identify obligations from provisions
- **review** → human validates AI extraction
- **map** → link obligations to controls/evidence
- **answer** → respond to compliance query with citations
- **alert** → notify of changes or gaps
- **remediate** → action taken to address gap

### Self-Reinforcing Loops

#### Loop 1: Source Expansion Loop
```
new source → parsed → normalized → obligations extracted → reviewed → searchable → knowledge expands
```

#### Loop 2: Query Gap Loop
```
user query → low confidence → flagged gap → source hunt → stronger future answers
```

#### Loop 3: Validation Loop
```
human validation → confidence recalibration → improved extraction precision
```

#### Loop 4: Change Impact Loop
```
regulation change → impacted obligations flagged → impacted controls flagged → remediation suggested
```

#### Loop 5: Policy Learning Loop
```
internal controls added → mapped to obligations → stronger compliance reasoning
```

### Patterns
- Recurring AML themes across regulators
- Regulator focus shifts over time
- Recurring control weaknesses
- Sector-specific compliance burdens

### Outcomes
- Better regulatory awareness
- Faster compliance responses
- Stronger control design
- Reduced blind spots
- Scalable regulatory intelligence

## Technical Architecture

### Stack
| Component | Technology |
|-----------|-----------|
| Frontend | React + TypeScript + Vite + Tailwind + shadcn/ui |
| Backend API | FastAPI (Python) with async SQLAlchemy |
| Database | SQLite (dev) / PostgreSQL (production-ready) |
| Search | Full-text search + vector similarity (SQLite FTS5 / pgvector) |
| Queue | In-process async workers (extensible to Redis + Celery) |
| Auth | JWT with RBAC (5 roles) |
| LLM Layer | Abstracted interface (provider-swappable) |
| Parser | Modular adapters (HTML, PDF, XML, structured pages) |

### Module Map

```
aml-compliance-os/
├── aml-backend/
│   ├── app/
│   │   ├── core/          # Auth, config, database
│   │   ├── models/        # Original AML models (entity, case, screening, etc.)
│   │   │   └── regulatory/  # NEW: Regulatory intelligence models
│   │   ├── routers/       # API endpoints
│   │   ├── services/      # Business logic
│   │   │   └── regulatory/  # NEW: Source registry, crawler, parser, etc.
│   │   ├── schemas/       # Pydantic schemas
│   │   └── utils/
│   ├── regulator_packs/   # NEW: Per-regulator configs and seed data
│   │   ├── fatf/
│   │   ├── saudi_aml/
│   │   ├── sama/
│   │   ├── cma/
│   │   └── insurance_authority/
│   └── tests/
├── aml-frontend/
│   └── src/
│       └── pages/
│           └── regulatory/  # NEW: Source monitor, change center, etc.
└── docs/                    # NEW: Architecture documentation
```

### Data Flow

```
┌─────────────┐    ┌──────────┐    ┌──────────┐    ┌─────────────┐
│  Regulator   │───▶│ Crawler  │───▶│  Parser  │───▶│ Normalizer  │
│  Source      │    │          │    │          │    │             │
└─────────────┘    └──────────┘    └──────────┘    └──────┬──────┘
                                                          │
                   ┌──────────────────────────────────────┘
                   ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Knowledge  │◀───│  Obligation  │◀───│   Change     │
│  Graph      │    │  Extractor   │    │  Detector    │
└──────┬──────┘    └──────────────┘    └──────────────┘
       │
       ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Hybrid     │───▶│  QA/Chat     │───▶│  Dashboard   │
│  Retrieval  │    │  Interface   │    │              │
└─────────────┘    └──────────────┘    └──────────────┘
```

### AI Agent Layer

| Agent | Responsibility |
|-------|---------------|
| Source Scout | Discover and register new regulatory sources |
| Change Detector | Monitor sources for updates, classify impact |
| Provision Parser | Extract structured sections from documents |
| Obligation Extractor | Identify obligations, prohibitions, deadlines |
| Topic Classifier | Assign topics and categories to provisions |
| Control Mapper | Link obligations to compliance controls |
| Conflict Detector | Find overlapping or conflicting obligations |
| Briefing Agent | Generate regulatory briefings and summaries |

All agents log their outputs for human review. No agent makes binding decisions.

## Source Trust Levels

| Tier | Description | Examples |
|------|-------------|---------|
| 1 | Official binding source | Laws, regulations, rulebooks |
| 2 | Official guidance/interpretive | FAQs, guidance docs, circulars |
| 3 | Draft/consultation | Consultation papers, draft rules |
| 4 | Secondary commentary | Industry analysis, news |

MVP defaults to Tier 1 and Tier 2 only.

## Security & Governance
- Role-based access control (Admin, Compliance Officer, Analyst, Auditor, Viewer)
- Immutable audit log with SHA-256 hash chain
- No silent overwriting of source snapshots
- All AI extractions require human review before becoming authoritative
- Provenance tracking on every piece of knowledge

## Phase P — Productization & Hardening

Phase P hardens the system for production use across 8 areas:

### P1: Data Integrity & Consistency
- Cross-link validation across the full entity chain (obligation -> control -> evidence -> risk -> audit -> issue -> remediation -> action)
- Orphan detection queries for all GRC entities
- FK constraint and cascading behavior verification
- API: `GET /api/admin/integrity/validate`, `GET /api/admin/integrity/chain-stats`

### P2: Auditability
- Extended audit logging to all GRC entities (EnterpriseRisk, Issue, RemediationAction, GRCAction, AuditFinding, ControlTest, ManagementResponse)
- Immutable audit trail with prev/new value tracking (JSON diff)
- SHA-256 hash chain for tamper detection
- API: `GET /api/admin/audit/trail`, `GET /api/admin/audit/entity/{entity_type}/{entity_id}`

### P3: Role & Access Model
- 5 roles: ADMIN, COMPLIANCE_OFFICER, ANALYST, AUDITOR, VIEWER
- Per-module read/write permissions matrix
- `require_roles()` decorator on all mutation endpoints
- API: `GET /api/admin/rbac/permissions`, `GET /api/admin/rbac/matrix`

### P4: Dashboard Trustworthiness
- Independent validation of every dashboard metric against raw DB counts
- No hardcoded values or approximations
- API: `GET /api/admin/dashboard/validate`

### P5: Error Handling & UX Reliability
- Removed all silent `.catch(() => {})` patterns in frontend
- Added visible error banners with dismissible state to all key GRC pages
- Proper HTTP status code checking on all fetch calls
- Loading spinners and empty states on all list pages

### P6: Performance & Scalability
- Recommended indexes for all frequently queried GRC fields (status, severity, priority, category, due_date, etc.)
- Index creation endpoint (idempotent, safe to call repeatedly)
- Table statistics and row count monitoring
- PostgreSQL migration readiness assessment
- API: `POST /api/admin/performance/ensure-indexes`, `GET /api/admin/performance/stats`

### P7: Export & Reporting
- CSV export: risk register, issues, actions, audit findings
- JSON export: executive report with all GRC metrics
- Streaming responses for large datasets
- API: `GET /api/admin/export/risks/csv`, `GET /api/admin/export/issues/csv`, etc.

### P8: Documentation
- Updated architecture.md (this document)
- Data model documentation for all GRC entities
- API endpoint catalog with OpenAPI/Swagger (auto-generated at `/docs`)
- System flow documentation

## GRC Data Model

### Entity Chain
```
Obligation --> Control --> Evidence
    |              |          |
    v              v          v
  Risk -------> Issue ----> Remediation ----> Action
    |              |                            |
    v              v                            v
  Snapshot    AuditFinding              ManagementResponse
                   ^
                   |
            AuditEngagement
                   ^
                   |
              AuditPlan
```

### Core GRC Models
| Model | Table | Key Fields |
|-------|-------|------------|
| EnterpriseRisk | grc_enterprise_risks | title, category, status, inherent_score, residual_score, treatment_strategy |
| Issue | grc_issues | title, source, severity, status, owner, due_date, aging_days |
| RemediationAction | grc_remediation_actions | title, status, target_date, issue_id |
| GRCAction | grc_actions | title, priority, status, source_type, origin, owner |
| AuditPlan | grc_audit_plans | title, status, planned_start, planned_end |
| AuditEngagement | grc_audit_engagements | title, status, plan_id, scope |
| ControlTest | grc_control_tests | control_id, engagement_id, result, tested_at |
| AuditFinding | grc_audit_findings | title, severity, status, engagement_id |
| ManagementResponse | grc_management_responses | finding_id, response_text, status |
| NarrativeSummary | grc_narrative_summaries | summary_type, content (AI-generated, clearly marked) |
| RiskSnapshot | grc_risk_snapshots | risk_id, snapshot_at, inherent_score, residual_score |

### Cross-Linking
All entities support cross-referencing via the cross-link service:
- Risk <-> Issue (risk materialization)
- Issue <-> Remediation (issue resolution)
- AuditFinding <-> ManagementResponse (finding closure)
- Action <-> any source entity (unified action tracking)

## API Endpoint Catalog

Full interactive API documentation available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Key Endpoint Groups
| Prefix | Module | Methods |
|--------|--------|---------|
| /api/grc/risks | Risk Register | GET, POST, PUT, DELETE |
| /api/grc/issues | Issue Management | GET, POST, PUT, DELETE |
| /api/grc/remediation | Remediation | GET, POST, PUT, DELETE |
| /api/grc/actions | Action Center | GET, POST, PUT, DELETE, scan-alerts, scan-patterns |
| /api/grc/audit-plans | Audit Plans | GET, POST, PUT, DELETE |
| /api/grc/audit-engagements | Audit Engagements | GET, POST, PUT, DELETE |
| /api/grc/control-tests | Control Tests | GET, POST, PUT, DELETE |
| /api/grc/audit-findings | Audit Findings | GET, POST, PUT, DELETE |
| /api/grc/management-responses | Management Responses | GET, POST, PUT, DELETE |
| /api/grc/narratives | Executive Narratives | GET, POST (AI-generated) |
| /api/grc/cross-links | Cross-Entity Links | GET |
| /api/grc/dashboard | GRC Dashboard | GET |
| /api/admin/* | Phase P Admin | Integrity, Audit, RBAC, Export, Performance |
