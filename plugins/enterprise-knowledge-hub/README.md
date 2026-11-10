# Enterprise Knowledge Hub (`enterprise-knowledge-hub`)

Synthesizes cross-source enterprise knowledge with citation conflict detection, jurisdiction- and effective-date-scoped SOP answering with deterministic abstention, and automated corpus freshness auditing.

## Included Workflow Skills

1. **`cross-source-knowledge-synthesis`** ([SKILL.md](skills/cross-source-knowledge-synthesis/SKILL.md)) — Ranks multi-repository passages by authority and freshness (`citation_conflict_auditor.py`), surfaces numerical and date contradictions across documents, and enforces 100% citation coverage.
2. **`policy-sop-answering`** ([SKILL.md](skills/policy-sop-answering/SKILL.md)) — Filters SOPs and HR/Finance/Legal policies by jurisdiction, legal entity, and effective date (`policy_scope_matcher.py`), rejecting superseded versions and abstaining when active coverage is missing.
3. **`knowledge-gap-freshness-audit`** ([SKILL.md](skills/knowledge-gap-freshness-audit/SKILL.md)) — Audits corpus metadata (`corpus_hygiene_scanner.py`) for overdue or null review timestamps, departed owners, near-duplicate titles, unpublished draft versions, and unindexed support ticket topics.

## Quickstart

- **1-Click Department Upload:** Upload `dist/bundles/enterprise-knowledge-hub.zip` into Gemini Agent.
- **Granular 1-Hop Upload:** Upload any single skill from `dist/skills/<skill-id>.zip`.
- **Tenant Customization:** Copy `.gemini-plugin/config.schema.json` properties into a tenant JSON file and run `python3 tools/package.py --org-config tenant.json --plugin enterprise-knowledge-hub`.
