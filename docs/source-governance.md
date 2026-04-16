# Source Governance Policy

## Trust Levels
| Tier | Description | Auto-ingest | Review Required |
|------|-------------|-------------|-----------------|
| 1 | Official binding (laws, regulations) | Yes | Obligations only |
| 2 | Official guidance (FAQs, circulars) | Yes | Obligations only |
| 3 | Draft/consultation papers | Manual only | Full review |
| 4 | Secondary commentary | Manual only | Full review |

## Ingestion Classes
1. **Canonical**: Laws, regulations, rulebooks, official circulars
2. **Interpretive**: FAQs, guidance, speeches, official notices
3. **Derived Internal**: Internal policies, controls, audit notes (future)

## Source Metadata Requirements
Every ingested source must have: authority_level, source_type, jurisdiction, regulator, language, parser_confidence, last_crawled

## Change Detection Rules
- Poll frequency: configurable per source (default: daily)
- Content hash comparison for change detection
- Impact classification: informational / interpretive / operational / material
- All material changes require human review within 48 hours

## Quality Controls
- No regulatory statement without citation
- No "binding" label without Tier 1 source metadata
- All AI extractions flagged for review
- Confidence scores on all extracted obligations
- Version history preserved (never overwrite snapshots)
