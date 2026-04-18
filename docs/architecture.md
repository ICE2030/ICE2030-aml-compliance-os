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
