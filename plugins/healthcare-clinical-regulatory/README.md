# Healthcare Clinical Trial, Pharmacovigilance & Prior Auth (`healthcare-clinical-regulatory`)

Validates clinical Schedule of Assessments schedules vs endpoints and enrollment capacity, checks E2B ICSR 4 minimum criteria and 7/15-day statutory clocks with PHI redaction alerts, and audits prior authorization packets against payer criteria. Pairs live `/work` connectors (`BigQuery, Google Drive, Google Docs, Google Sheets`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Clinical Operations / Study Feasibility Lead | Auditing Phase II/III Schedule of Assessments (SoA) visits against primary efficacy endpoints | [`clinical-protocol-feasibility`](skills/clinical-protocol-feasibility/README.md) | `scripts/soa_endpoint_validator.py` |
| Pharmacovigilance / Drug Safety Specialist | Screening incoming E2B Individual Case Safety Reports (ICSRs) for regulatory clocks | [`pharmacovigilance-safety-intake`](skills/pharmacovigilance-safety-intake/README.md) | `scripts/icsr_completeness_checker.py` |
| Utilization Management Nurse / Medical Reviewer | Evaluating biologic/specialty prior-authorization packets against payer clinical policies | [`prior-auth-medical-necessity`](skills/prior-auth-medical-necessity/README.md) | `scripts/medical_criteria_matcher.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`healthcare-clinical-regulatory.zip`](../../dist/bundles/healthcare-clinical-regulatory.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/clinical-protocol-feasibility.zip`](../../dist/skills/clinical-protocol-feasibility.zip) — Detects missing endpoint procedures in trial Schedules of Assessments and projects net IRB-approved screen-adjusted enrollment.
  - [`dist/skills/pharmacovigilance-safety-intake.zip`](../../dist/skills/pharmacovigilance-safety-intake.zip) — Validates 4 ICH minimum ICSR criteria, calculates 7-day/15-day/90-day statutory clocks from awareness_date, and traps raw PHI leaks.
  - [`dist/skills/prior-auth-medical-necessity.zip`](../../dist/skills/prior-auth-medical-necessity.zip) — Matches CPT prior-auth packets against covered ICD-10 prefixes, step-therapy trial durations, and required diagnostic labs.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`healthcare-clinical-regulatory.zip`](../../dist/bundles/healthcare-clinical-regulatory.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/healthcare-clinical-regulatory` / `@healthcare-clinical-regulatory` so Layer 1 (`remote_cli mcp`) pulls live data from `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets` or `Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` (`5,814 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Clinical_SOA_Visits`, `Trial_Endpoints`, `Clinical_Trial_Sites`, `ICSR_Pharmacovigilance_Cases`, `Payer_Medical_Policies`, `Prior_Auth_Requests`)](../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx):

```bash
python3 plugins/healthcare-clinical-regulatory/skills/clinical-protocol-feasibility/scripts/soa_endpoint_validator.py \
  --input examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx \
  --config plugins/healthcare-clinical-regulatory/skills/clinical-protocol-feasibility/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`.
- **Customer BYO-MCP Servers**: `Claims / EHR Clearinghouse & CTMS Safety Gateway MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Fetch de-identified clinical protocol Schedules of Assessments, ICSR adverse-event safety intakes, and prior-auth medical policy criteria from BigQuery or customer CTMS/Clearinghouse MCP servers via remote_cli mcp before Python validation.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` (`5,814 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Clinical_SOA_Visits`, `Trial_Endpoints`, `Clinical_Trial_Sites`, `ICSR_Pharmacovigilance_Cases`, `Payer_Medical_Policies`, `Prior_Auth_Requests`)](../../examples/healthcare-clinical-regulatory/Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`commercial-contract-baseline.md`](../../shared/baselines/commercial-contract-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Submitting E2B regulatory safety reports to FDA/EMA/PMDA via customer Safety MCP; Finalizing clinical prior-authorization medical necessity approvals or denials via Clearinghouse MCP.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Unredacted SSN, email, or phone PHI detection and masking inside narrative outputs; Fatal/life-threatening 7-day SUSAR vs 15-day statutory reporting deadline and 4-criteria check; Step-therapy completion verification (never conflating active ongoing therapy with completed prerequisites).
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Daily Pharmacovigilance ICSR SLA Watch" on cron `0 7 * * *` (`UTC`) with instruction: "Run the daily pharmacovigilance intake check via scripts/icsr_completeness_checker.py to watch 7-day fatal SUSAR clocks, incomplete 4-criteria cases, and raw PHI alerts.""*

## Example Queries & Verified Outcomes

- **`clinical-protocol-feasibility`** ([skill guide](skills/clinical-protocol-feasibility/README.md)): Connector prompt: *"Audit Meridian BioPharma Phase III protocol where Day-180 Visit omits the biopsy required for the Primary Endpoint."* Verified starter check against `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` (`134.2 ms`): `protocol_id=APX-ONC-301`, `endpoints_checked=2`, `soa_endpoint_gap_count=2`, `target_sample_size=240`.
- **`pharmacovigilance-safety-intake`** ([skill guide](skills/pharmacovigilance-safety-intake/README.md)): Connector prompt: *"Screen Meridian BioPharma safety cases including a fatal unexpected SUSAR aware on 2026-11-05 as of 2026-11-10."* Verified starter check against `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` (`134.8 ms`): `cases_screened=2`, `valid_icsr_count=2`, `phi_redaction_alerts=1`, `urgent_or_overdue_count=1`.
- **`prior-auth-medical-necessity`** ([skill guide](skills/prior-auth-medical-necessity/README.md)): Connector prompt: *"Evaluate prior auth PA-401 for biologic therapy requiring two >=30-day step failures when patient completed only one 14-day trial."* Verified starter check against `Apex_Clinical_Protocol_PV_and_PriorAuth_Sample.xlsx` (`147.9 ms`): `requests_evaluated=2`, `criteria_met_count=1`, `gap_or_review_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-16`** (`6 tabs, 4,610 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.972 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.950 / 1.000`) and `Prose-Only Baseline` (`PASS 0.980 / 1.000`). Verified domain traps: Protocol SoA procedure vs efficacy endpoint matrix mismatch; Fatal/life-threatening unexpected 7-day SUSAR window + PHI email/phone leak; Completed vs ongoing step-therapy prior-auth distinction.
