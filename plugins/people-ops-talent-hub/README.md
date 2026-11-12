# People Ops, Talent Calibration & Workforce Analytics (`people-ops-talent-hub`)

Calibrates structured interview scorecards for score dispersion and bias signals, orchestrates 30/60/90 onboarding plans with mandatory Day-1 gate checks, and audits effective-dated Workday compensation bands with FTE/CWK separation and small-cell privacy redaction. Pairs live `/work` connectors (`Google Drive, Google Docs, Google Sheets, Gmail, ServiceNow, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Recruiting & Talent Bar Lead | Calibrating multi-interviewer hiring scorecards prior to hiring committee review | [`structured-hiring-rubric`](skills/structured-hiring-rubric/README.md) | `scripts/rubric_calibration_checker.py` |
| People Ops Onboarding Specialist | Tracking Day-1 readiness across IT provisioning, security training, and manager tasks | [`employee-onboarding-navigator`](skills/employee-onboarding-navigator/README.md) | `scripts/onboarding_plan_builder.py` |
| Compensation Committee / Total Rewards Lead | Running annual pay-equity, compa-ratio, and attrition audits across global entities | [`workforce-attrition-comp-audit`](skills/workforce-attrition-comp-audit/README.md) | `scripts/comp_band_analyzer.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`people-ops-talent-hub.zip`](../../dist/bundles/people-ops-talent-hub.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/structured-hiring-rubric.zip`](../../dist/skills/structured-hiring-rubric.zip) — Audits 1-4 interview scorecards for >=2.0 dispersion, thin behavioral evidence (<40 chars), and protected-class bias signals.
  - [`dist/skills/employee-onboarding-navigator.zip`](../../dist/skills/employee-onboarding-navigator.zip) — Tracks 30/60/90 onboarding milestones, enforces mandatory Day-1 IT/security gates, and detects blocked upstream dependencies.
  - [`dist/skills/workforce-attrition-comp-audit.zip`](../../dist/skills/workforce-attrition-comp-audit.zip) — Deduplicates effective-dated HRIS rows, isolates CWKs from FTEs, normalizes hourly/monthly/FX pay, and suppresses <5 privacy cells.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`people-ops-talent-hub.zip`](../../dist/bundles/people-ops-talent-hub.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/people-ops-talent-hub` / `@people-ops-talent-hub` so Layer 1 (`remote_cli mcp`) pulls live data from `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` or `Workday HRIS & ATS Scorecard MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` (`6,050 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Workforce_HRIS_Roster`, `Comp_Bands_Master`, `FX_Rates`, `Hiring_Panel_Scorecards`, `Onboarding_Tasks_Plan`)](../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx):

```bash
python3 plugins/people-ops-talent-hub/skills/structured-hiring-rubric/scripts/rubric_calibration_checker.py \
  --input examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx \
  --config plugins/people-ops-talent-hub/skills/structured-hiring-rubric/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`.
- **Customer BYO-MCP Servers**: `Workday HRIS & ATS Scorecard MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Retrieve effective-dated employee compensation rosters, contingent-worker flags, interview scorecards, and onboarding task gates from Google Sheets/ServiceNow or customer Workday/ATS MCP servers via remote_cli mcp before Python HR analytics.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` (`6,050 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Workforce_HRIS_Roster`, `Comp_Bands_Master`, `FX_Rates`, `Hiring_Panel_Scorecards`, `Onboarding_Tasks_Plan`)](../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`hr-hiring-comp-baseline.md`](../../shared/baselines/hr-hiring-comp-baseline.md) and [`workday-hris-traps.md`](../../shared/traps/workday-hris-traps.md), [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Proposing or committing compensation adjustments in customer Workday HRIS MCP; Advancing candidate offer stages or dispatching hiring letters via customer ATS MCP / Gmail.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Strict small-cohort n < min_privacy_group_size (n < 5) k-anonymity salary & attrition redaction; Effective-date deduplication, Contingent Worker (CWK) isolation from FTE totals, and EUR/GBP monthly FX normalization; Scorecard bias/halo variance alert preventing autonomous hiring recommendations.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly Onboarding Stall Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly onboarding gate check via scripts/onboarding_plan_builder.py to detect missing Day-1 IT/security gates and stalled 30/60/90 milestones.""*

## Example Queries & Verified Outcomes

- **`structured-hiring-rubric`** ([skill guide](skills/structured-hiring-rubric/README.md)): Connector prompt: *"Calibrate Greenhouse scorecards for Cymbal Financial Staff Engineer candidate with scores [4, 1, 4, 3]."* Verified starter check against `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` (`148.3 ms`): `candidates_reviewed=2`, `hire_recommended_count=1`, `debrief_required_count=0`, `blocked_bias_or_evidence_count=1`.
- **`employee-onboarding-navigator`** ([skill guide](skills/employee-onboarding-navigator/README.md)): Connector prompt: *"Check upcoming Stratos Telecom hires in Workday/ServiceNow HRSD for missing laptop or SSO gates."* Verified starter check against `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` (`144.4 ms`): `hires_tracked=2`, `stalled_or_at_risk_count=2`, `total_overdue_tasks=1`, `missing_day1_gate_hires=2`.
- **`workforce-attrition-comp-audit`** ([skill guide](skills/workforce-attrition-comp-audit/README.md)): Connector prompt: *"Audit Workday roster where promoted employees have 3 historical effective_date rows plus 1 future-dated row and 4 CWKs."* Verified starter check against `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` (`161.7 ms`): `raw_rows_processed=17`, `historical_snapshots_collapsed=1`, `future_effective_rows_excluded=0`, `unique_fte_count=15`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-08`** (`6 tabs, 4,196 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.993 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`FAIL 0.679 / 1.000`) and `Prose-Only Baseline` (`FAIL 0.695 / 1.000`). Verified domain traps: Effective-date historical snapshot deduplication; Contingent worker (CWK) isolation from FTE base; EUR monthly to USD annual FX normalization; Mandatory n < 5 cohort privacy suppression (Legal n=3, Strategy n=4).
