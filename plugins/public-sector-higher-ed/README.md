# Public Sector Casework, Grants & Higher-Ed Ops (`public-sector-higher-ed`)

Evaluates citizen benefits/aid eligibility with strict missing-document cure holds (never silent denials) and SSN redaction, scores public procurement tenders after mandatory debarment/COI pass-fail gates, and validates research grant budgets (F&A indirect caps, unallowables, PI effort) plus accreditation evidence freshness. Pairs live `/work` connectors (`ServiceNow, BigQuery, Google Drive, Google Docs, Google Sheets, Box`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Public Benefits Eligibility Supervisor | Auditing citizen assistance intake packets against Federal Poverty Level (`200% FPL`) statutes | [`citizen-case-eligibility-triager`](skills/citizen-case-eligibility-triager/README.md) | `scripts/statutory_eligibility_engine.py` |
| Public Procurement / Contracting Officer | Scoring multi-vendor government RFP responses across weighted technical, sustainability, and price criteria | [`procurement-tender-evaluator`](skills/procurement-tender-evaluator/README.md) | `scripts/tender_weighted_scorer.py` |
| Sponsored Research / University Grants Controller | Validating federal/institutional grant budgets before submission or audit drawdowns | [`grant-accreditation-evidence-pack`](skills/grant-accreditation-evidence-pack/README.md) | `scripts/grant_accreditation_validator.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`public-sector-higher-ed.zip`](../../dist/bundles/public-sector-higher-ed.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/citizen-case-eligibility-triager.zip`](../../dist/skills/citizen-case-eligibility-triager.zip) — Computes household FPL income eligibility, enforces missing-document cure holds instead of silent denials, and counts PII redactions.
  - [`dist/skills/procurement-tender-evaluator.zip`](../../dist/skills/procurement-tender-evaluator.zip) — Enforces mandatory debarment/COI/tax pass-fail gates first, then computes lowest-compliant commercial normalization and weighted rank.
  - [`dist/skills/grant-accreditation-evidence-pack.zip`](../../dist/skills/grant-accreditation-evidence-pack.zip) — Validates MTDC base vs F&A indirect cost caps, flags unallowable expenses, checks PI 100% effort cap, and checks accreditation freshness.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`public-sector-higher-ed.zip`](../../dist/bundles/public-sector-higher-ed.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/public-sector-higher-ed` / `@public-sector-higher-ed` so Layer 1 (`remote_cli mcp`) pulls live data from `ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box` or `Grants Management & Procurement Portal MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` (`5,129 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Citizen_Benefit_Cases`, `Procurement_Tender_Bids`, `Grant_Budget_Lines`, `PI_Effort_Allocations`, `Accreditation_Artifacts`)](../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx):

```bash
python3 plugins/public-sector-higher-ed/skills/citizen-case-eligibility-triager/scripts/statutory_eligibility_engine.py \
  --input examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx \
  --config plugins/public-sector-higher-ed/skills/citizen-case-eligibility-triager/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `ServiceNow`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Box`.
- **Customer BYO-MCP Servers**: `Grants Management & Procurement Portal MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Query citizen benefit case packets, sealed vendor tender matrices, and sponsored research budgets/PI effort logs from ServiceNow, BigQuery, Drive, or Grants/Procurement MCP servers via remote_cli mcp before Python compliance validation.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` (`5,129 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Citizen_Benefit_Cases`, `Procurement_Tender_Bids`, `Grant_Budget_Lines`, `PI_Effort_Allocations`, `Accreditation_Artifacts`)](../../examples/public-sector-higher-ed/Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`commercial-contract-baseline.md`](../../shared/baselines/commercial-contract-baseline.md), [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md) and [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md), [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`servicenow-jira-itsm-traps.md`](../../shared/traps/servicenow-jira-itsm-traps.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Issuing statutory citizen benefit eligibility determinations or cure notices via ServiceNow/Case MCP; Recording procurement tender award selections via customer Procurement Portal MCP; Submitting federal/sponsor grant budget certifications via customer Grants Management MCP.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Debarred/ineligible vendor hard disqualification blocking award when zero compliant bids exist; MTDC indirect-cost exemption exclusion (equipment/subawards >$25k), unallowable cost blocker, and PI >100% effort cap; Deterministic PENDING_CURE_NOTICE handling preventing silent denial of incomplete citizen packets.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly Grant & Accreditation Evidence Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly sponsored grant allowability and accreditation artifact freshness check via scripts/grant_accreditation_validator.py across active institutional packets.""*

## Example Queries & Verified Outcomes

- **`citizen-case-eligibility-triager`** ([skill guide](skills/citizen-case-eligibility-triager/README.md)): Connector prompt: *"Triage CivicFirst Agency household-of-4 packet missing proof_of_income with an SSN in free-text notes."* Verified starter check against `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` (`138.3 ms`): `cases_triaged=2`, `eligible_count=1`, `pending_cure_count=1`, `recommended_denials=0`.
- **`procurement-tender-evaluator`** ([skill guide](skills/procurement-tender-evaluator/README.md)): Connector prompt: *"Evaluate CivicFirst Agency RFP bids where a $120k vendor is debarred/sanctioned and compliant bids are $200k and $250k."* Verified starter check against `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` (`135.3 ms`): `tender_id=RFP-CIVIC-2026-09`, `bids_received=3`, `compliant_bids=2`, `disqualified_bids=1`.
- **`grant-accreditation-evidence-pack`** ([skill guide](skills/grant-accreditation-evidence-pack/README.md)): Connector prompt: *"Audit Cascade State University grant packet with $4k lobbying line, excess F&A above 52% MTDC, and 115% PI effort."* Verified starter check against `Apex_Public_Sector_Eligibility_Tender_and_Grant_Sample.xlsx` (`136.6 ms`): `award_or_review_id=CSU-BIO-440`, `mtdc_base_usd=140000.0`, `indirect_fa_requested_usd=52000.0`, `max_allowed_indirect_usd=36400.0`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-20`** (`34-page Solicitation & Grant PDF`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.996 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.880 / 0.750`) and `Prose-Only Baseline` (`PASS 0.880 / 0.750`). Verified domain traps: Debarred lowest-bidder disqualification; MTDC capital-equipment & unallowable lobbying exclusion before 26% F&A cap; PI >100% effort cap (115%) + cost-share shortfall; Missing-document PENDING_CURE_NOTICE vs improper denial.
