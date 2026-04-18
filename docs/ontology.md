# AML Compliance OS - Data Ontology

## Core Entity-Relationship Model

```
Jurisdiction ──has_many──▶ Regulator
Regulator ──issues──▶ Source
Source ──has_many──▶ SourceVersion
SourceVersion ──contains──▶ Document
Document ──has_many──▶ Provision
Provision ──creates──▶ Obligation
Obligation ──satisfied_by──▶ Control
Control ──evidenced_by──▶ EvidenceArtifact
Obligation ──if_unmet──▶ Risk
Risk ──triggers──▶ RegulatoryAction
```

## Entity Definitions

### Jurisdiction
Geographic or political territory where regulations apply.
- id, name, name_ar, code (ISO 3166), region, is_active

### Regulator
Regulatory body that issues and enforces rules.
- id, name, name_ar, abbreviation, jurisdiction_id, website, source_url, regulator_type, is_active

### Source
A registered regulatory document or page to monitor.
- id, regulator_id, title, title_ar, url, source_type (law/regulation/guidance/circular/faq), authority_level (tier 1-4), jurisdiction_id, language, is_monitored, crawl_frequency, last_crawled, status

### SourceVersion
A point-in-time snapshot of a source.
- id, source_id, version_number, fetched_at, content_hash, raw_content, parsed_content, change_summary, is_current

### Document
A parsed, structured regulatory document.
- id, source_version_id, title, title_ar, document_type, effective_date, publication_date, regulator_id, jurisdiction_id, topics, language, status

### Provision
A specific section, article, or clause within a document.
- id, document_id, section_number, title, text, text_ar, provision_type (article/clause/definition/schedule), parent_provision_id, order_index

### Obligation
A mandatory requirement, prohibition, or condition extracted from a provision.
- id, provision_id, text, normalized_summary, obligation_type (mandatory/prohibition/reporting/deadline/threshold), applies_to_entity_types, applies_to_product_types, condition, deadline, confidence, extraction_method, review_status, reviewer_notes

### Control
A policy, procedure, or workflow that satisfies an obligation.
- id, name, description, control_type (policy/procedure/technical/monitoring), owner, status, effectiveness_rating

### EvidenceArtifact
Proof that a control is operating effectively.
- id, control_id, artifact_type (document/log/attestation/report), description, file_path, collected_at, status

### Risk
The consequence of not meeting an obligation.
- id, obligation_id, risk_type (regulatory/financial/reputational/operational), severity, likelihood, description, mitigation_status

### Topic
A regulatory subject area for classification.
- id, name, name_ar, parent_topic_id, category (aml/ctf/kyc/sanctions/pep/reporting/governance/fintech/data_protection/licensing)

### ChangeEvent
A detected change in a monitored source.
- id, source_id, old_version_id, new_version_id, detected_at, change_type (new_document/content_modified/section_added/section_removed), impact_level (informational/interpretive/operational/material), summary, affected_provisions, affected_obligations, review_status

### ReviewDecision
Human validation of AI-extracted content.
- id, content_type, content_id, reviewer_id, decision (approved/rejected/needs_revision), confidence_adjustment, notes, reviewed_at

### QueryLog
Record of user queries for gap detection.
- id, user_id, query_text, response_confidence, sources_used, gaps_detected, feedback_rating, created_at

### RegulatoryAction
Enforcement or remediation action.
- id, obligation_id, action_type (filing/remediation/training/policy_update/control_enhancement), description, deadline, status, assigned_to

## Key Relationships

| Relationship | From | To | Meaning |
|-------------|------|-----|---------|
| issued_by | Source | Regulator | Source was published by regulator |
| applies_to | Obligation | EntityType/ProductType | Who must comply |
| supersedes | Source | Source | New source replaces old |
| amends | Source | Source | New source modifies old |
| references | Provision | Provision | Cross-reference |
| requires | Obligation | Control | Control needed |
| evidenced_by | Control | EvidenceArtifact | Proof of compliance |
| related_to | Topic | Topic | Thematic link |
| overlaps_with | Obligation | Obligation | Similar requirements |
| conflicts_with | Obligation | Obligation | Contradictory requirements |
| derived_from | Obligation | Provision | Extraction source |
| monitored_by | Source | ChangeEvent | Change tracking |
