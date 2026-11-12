# ITSM & Service Desk Command Center (`itsm-command-center`)

Accelerates incident triage with business-elapsed SLA breach tracking and spike clustering, scores CAB change requests against freeze windows and blast radius, and mines resolved tickets for Problem candidates and KCS deflection savings. Pairs live `/work` connectors (`ServiceNow, Jira, Confluence, Google Drive, Google Sheets, Google Docs, Slack`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Major Incident Manager / Duty SRE | Triaging active ServiceNow or Jira Service Management Sev-1/2 queues | [`incident-triage-routing`](skills/incident-triage-routing/README.md) | `scripts/sla_cluster_triage.py` |
| Change Advisory Board (CAB) Chair | Evaluating production database, payment, or Tier-0 changes ahead of deployment windows | [`change-risk-cab-review`](skills/change-risk-cab-review/README.md) | `scripts/cab_risk_scorer.py` |
| Problem Management Lead | Mining closed incident backlogs for recurring root causes | [`problem-rca-kb-generator`](skills/problem-rca-kb-generator/README.md) | `scripts/kcs_deflection_analyzer.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`itsm-command-center.zip`](../../dist/bundles/itsm-command-center.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/incident-triage-routing.zip`](../../dist/skills/incident-triage-routing.zip) — Computes business-elapsed vs wall-clock SLA risk, clusters correlated incident spikes by CI and error signature, and ranks matching runbooks.
  - [`dist/skills/change-risk-cab-review.zip`](../../dist/skills/change-risk-cab-review.zip) — Scores ServiceNow and Jira change requests across blast radius, freeze-window collisions, rollback validation, CI failure history, and CAB tier.
  - [`dist/skills/problem-rca-kb-generator.zip`](../../dist/skills/problem-rca-kb-generator.zip) — Groups repeat resolved tickets into Problem candidates, calculates MTTR and annualized L1 deflection savings, and validates KCS draft completeness.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`itsm-command-center.zip`](../../dist/bundles/itsm-command-center.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/itsm-command-center` / `@itsm-command-center` so Layer 1 (`remote_cli mcp`) pulls live data from `ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` (`5,998 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Incident_Sev_Queue`, `Runbooks_Catalog`, `Change_CAB_Requests`, `Freeze_Windows`, `Problem_Tickets_Archive`, `KCS_Drafts`)](../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx):

```bash
python3 plugins/itsm-command-center/skills/incident-triage-routing/scripts/sla_cluster_triage.py \
  --input examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx \
  --config plugins/itsm-command-center/skills/incident-triage-routing/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack`.
- **Connector Fetch Guidance**: Query active ServiceNow incidents (sysparm_display_value=all), CAB changes, and CMDB CIs, Jira issues, and Confluence KCS runbooks via remote_cli mcp (capped to targeted batch lookups) before Python SLA clustering and CAB scoring.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` (`5,998 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Incident_Sev_Queue`, `Runbooks_Catalog`, `Change_CAB_Requests`, `Freeze_Windows`, `Problem_Tickets_Archive`, `KCS_Drafts`)](../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`servicenow-jira-itsm-traps.md`](../../shared/traps/servicenow-jira-itsm-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Reassigning P1/P2 incidents or updating ServiceNow/Jira tickets in bulk; Approving or rejecting CAB change requests in ServiceNow; Publishing KCS knowledge articles to external service portals in Confluence or ServiceNow.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: ServiceNow state=8 canceled exclusion and business_elapsed_minutes vs wall-clock SLA enforcement; CAB freeze-window collision, missing backout-plan verification, and blast-radius risk scoring; Single-pass multi-tab workbook and capped <=3 ITSM/KB search execution discipline.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Hourly SLA Breach Watch" on cron `0 * * * *` (`UTC`) with instruction: "Execute hourly incident triage and SLA breach scan via scripts/sla_cluster_triage.py. Highlight active P1/P2 tickets above 75% business-elapsed SLA budget, flag emerging CI/error spike clusters, and recommend top matching runbooks without mutating ticket assignments automatically.""*

## Example Queries & Verified Outcomes

- **`incident-triage-routing`** ([skill guide](skills/incident-triage-routing/README.md)): Connector prompt: *"Triage Cymbal Financial's active ServiceNow incident queue, excluding canceled tickets and subtracting paused hold time from SLA burn."* Verified starter check against `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` (`146.7 ms`): `total_records_received=4`, `active_incident_count=4`, `closed_excluded_count=0`, `canceled_excluded_count=0`.
- **`change-risk-cab-review`** ([skill guide](skills/change-risk-cab-review/README.md)): Connector prompt: *"Score Stratos Telecom's pending Thursday night ServiceNow changes against the Q4 Freeze Window calendar."* Verified starter check against `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` (`157.6 ms`): `change_count=2`, `high_or_emergency_count=1`, `freeze_collision_count=1`, `max_risk_score=85`.
- **`problem-rca-kb-generator`** ([skill guide](skills/problem-rca-kb-generator/README.md)): Connector prompt: *"Analyze the last 90 days of Apex Manufacturing ServiceNow tickets to identify top Problem candidates and KCS deflection ROI."* Verified starter check against `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` (`143.7 ms`): `total_tickets_scanned=4`, `open_unresolved_excluded=0`, `canceled_excluded=0`, `problem_candidate_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-12`** (`6 tabs, 4,411 rows (.xlsx) + 24-page Runbook PDF`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`FAIL (0.373 comp / 0.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.983 / 1.000`) and `Prose-Only Baseline` (`PASS 0.920 / 1.000`). Verified domain traps: Holiday Change Freeze collision on Tier-0 payments change; Missing rollback plan risk scoring (score 85 block); Checkout P1 burst clustering to RB-PAYMENT-POOL runbook.
