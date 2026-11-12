# SDLC Modernization, Security PR & SRE Ops (`sdlc-modernization-sre`)

Reverse-engineers legacy codebases into PRD traceability matrices, computes exact SLO error-budget burn and TTD/TTM/TTR postmortem timelines, and gates PR diffs for secrets, removed authz checks, and unsafe DB migrations. Pairs live `/work` connectors (`GitHub, Jira, Confluence, BigQuery, Google Drive, Google Docs, Google Sheets, Slack`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Principal Modernization Architect | Decomposing monolithic services and database tables into target microservices | [`legacy-code-to-prd`](skills/legacy-code-to-prd/README.md) | `scripts/spec_traceability_matrix.py` |
| Site Reliability Engineer (SRE) | Reconciling outage timelines and SLO error-budget consumption after multi-service incidents | [`sre-incident-postmortem`](skills/sre-incident-postmortem/README.md) | `scripts/slo_timeline_calculator.py` |
| AppSec / DevSecOps Reviewer | Auditing high-risk authentication, billing, and schema-migration pull requests | [`security-pr-readiness-gate`](skills/security-pr-readiness-gate/README.md) | `scripts/diff_risk_inspector.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`sdlc-modernization-sre.zip`](../../dist/bundles/sdlc-modernization-sre.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/legacy-code-to-prd.zip`](../../dist/skills/legacy-code-to-prd.zip) — Parses legacy code inventories for entrypoints, DB read/write couplings, complexity hotspots, and requirement-to-test traceability coverage.
  - [`dist/skills/sre-incident-postmortem.zip`](../../dist/skills/sre-incident-postmortem.zip) — Computes error-budget burn rates, TTD/TTM/TTR intervals, availability impact, and postmortem action-item SLA compliance.
  - [`dist/skills/security-pr-readiness-gate.zip`](../../dist/skills/security-pr-readiness-gate.zip) — Scans unified PR diffs and dependency manifests for hardcoded secrets, removed authz checks, unsafe migrations, and breaking API changes.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`sdlc-modernization-sre.zip`](../../dist/bundles/sdlc-modernization-sre.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/sdlc-modernization-sre` / `@sdlc-modernization-sre` so Layer 1 (`remote_cli mcp`) pulls live data from `GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` (`5,938 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Service_Modules_Inventory`, `PRD_Requirements`, `Test_Coverage`, `Incident_Outages`, `Postmortem_Action_Items`, `PR_Dependencies`)](../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx):

```bash
python3 plugins/sdlc-modernization-sre/skills/legacy-code-to-prd/scripts/spec_traceability_matrix.py \
  --input examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx \
  --config plugins/sdlc-modernization-sre/skills/legacy-code-to-prd/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack`.
- **Connector Fetch Guidance**: Pull PR diffs, CI test manifests, incident timeline logs, and Jira postmortem action queues from GitHub, Jira, Confluence, and BigQuery via remote_cli mcp before running Python traceability, SLO interval, and diff-risk checks.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` (`5,938 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Service_Modules_Inventory`, `PRD_Requirements`, `Test_Coverage`, `Incident_Outages`, `Postmortem_Action_Items`, `PR_Dependencies`)](../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`servicenow-jira-itsm-traps.md`](../../shared/traps/servicenow-jira-itsm-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Submitting GitHub PR reviews, merge approvals, or protected-branch status updates; Bulk-creating or updating Jira postmortem remediation tickets and owners; Executing or scheduling database DDL/schema migrations flagged as blocking.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Hardcoded secret, removed auth decorator, and unsafe/blocking DDL migration merge blocker; Outage interval union-merge deduplication preventing overlapping windows from overstating TTR/SLO burn; Strict legacy requirement-to-test traceability matrix coverage check.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly SRE SLO & Postmortem Review" on cron `0 9 * * 1` (`UTC`) with instruction: "Run the weekly SRE reliability and postmortem action-item SLA audit via scripts/slo_timeline_calculator.py. Compute 30-day error-budget consumption across P1/P2 incidents, report TTD/TTM/TTR trends, and flag overdue postmortem corrective actions without mutating Jira issues autonomously.""*

## Example Queries & Verified Outcomes

- **`legacy-code-to-prd`** ([skill guide](skills/legacy-code-to-prd/README.md)): Connector prompt: *"Parse Cymbal Financial's legacy settlement service modules in GitHub and extract DB couplings and complexity hotspots."* Verified starter check against `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` (`148.4 ms`): `module_count=2`, `hotspot_count=1`, `db_table_count=3`, `requirement_count=3`.
- **`sre-incident-postmortem`** ([skill guide](skills/sre-incident-postmortem/README.md)): Connector prompt: *"Compute 30-day SLO error-budget burn and TTD/TTM/TTR intervals for Stratos Telecom's core auth incidents."* Verified starter check against `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` (`143.1 ms`): `slo_target_pct=99.9`, `window_days=30`, `monthly_error_budget_minutes=43.2`, `total_minutes_burned=144.0`.
- **`security-pr-readiness-gate`** ([skill guide](skills/security-pr-readiness-gate/README.md)): Connector prompt: *"Review PR #412 on Veloce SuperApp's checkout service before I approve and merge it."* Verified starter check against `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` (`149.1 ms`): `pr_id=PR-APX-142`, `secret_finding_count=1`, `removed_authz_count=1`, `migration_risk_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-09`** (`6 tabs, 4,411 rows (.xlsx) + 27-page .docx + 24-page PDF`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`FAIL (0.775 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`FAIL 0.440 / 0.000`) and `Prose-Only Baseline` (`FAIL 0.793 / 1.000`). Verified domain traps: Overlapping outage interval merging (92m naive sum -> 65m union); Superseded v1.0 vs approved v2.1 circuit breaker selection; Auth decorator removal + hardcoded secret + non-concurrent DB index DDL.
