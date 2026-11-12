# Customer Operations, VIP Escalation & Knowledge Quality (`customer-operations-escalation`)

Scores VIP account escalations by ARR exposure and Sev1 outages, mines CSAT/NPS verbatims into ARR-weighted driver paretos with null-rating hygiene, and validates support troubleshooting decision trees for graph defects. Pairs live `/work` connectors (`Salesforce, ServiceNow, Google Docs, Google Sheets, Google Drive, Slack`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| VP of Customer Support / Escalation Manager | Prioritizing multi-customer Sev-1 incidents into daily executive war rooms | [`critical-escalation-warroom`](skills/critical-escalation-warroom/README.md) | `scripts/escalation_exposure_scorer.py` |
| Voice of Customer (VoC) & CX Lead | Auditing high blended CSAT averages (`4.99`) that hide high-ARR cancellation risk | [`csat-churn-signal-miner`](skills/csat-churn-signal-miner/README.md) | `scripts/verbatim_driver_quantifier.py` |
| Support Operations Architect | Validating guided diagnostic flows before publishing to Tier-1 agents or self-service bots | [`troubleshooting-tree-author`](skills/troubleshooting-tree-author/README.md) | `scripts/decision_tree_validator.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`customer-operations-escalation.zip`](../../dist/bundles/customer-operations-escalation.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/critical-escalation-warroom.zip`](../../dist/skills/critical-escalation-warroom.zip) — Scores VIP account escalations (0-100) from Sev1/Sev2 cases, SLA breaches, ARR, imminent renewals, outages, and competitor risk.
  - [`dist/skills/csat-churn-signal-miner.zip`](../../dist/skills/csat-churn-signal-miner.zip) — Classifies survey verbatims into ARR-weighted friction drivers, excludes null scores from averages, and catches explicit churn intent.
  - [`dist/skills/troubleshooting-tree-author.zip`](../../dist/skills/troubleshooting-tree-author.zip) — Validates customer support diagnostic trees via BFS/DFS for cycles, dead-end questions, orphan nodes, broken refs, and depth.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`customer-operations-escalation.zip`](../../dist/bundles/customer-operations-escalation.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/customer-operations-escalation` / `@customer-operations-escalation` so Layer 1 (`remote_cli mcp`) pulls live data from `Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` (`4,345 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Customer_Escalation_Warroom`, `CSAT_Churn_Verbatims`, `Troubleshooting_Decision_Tree`)](../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx):

```bash
python3 plugins/customer-operations-escalation/skills/critical-escalation-warroom/scripts/escalation_exposure_scorer.py \
  --input examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx \
  --config plugins/customer-operations-escalation/skills/critical-escalation-warroom/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack`.
- **Connector Fetch Guidance**: Pull active customer account ARR/renewal windows from Salesforce and open CSM escalation cases, SLA timers, and CSAT verbatims from ServiceNow or Google Sheets via remote_cli mcp before scoring exposure in Python.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` (`4,345 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Customer_Escalation_Warroom`, `CSAT_Churn_Verbatims`, `Troubleshooting_Decision_Tree`)](../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`salesforce-crm-soql-traps.md`](../../shared/traps/salesforce-crm-soql-traps.md), [`servicenow-jira-itsm-traps.md`](../../shared/traps/servicenow-jira-itsm-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Creating executive customer war-rooms or paging VP sponsors via ServiceNow or Slack; Publishing interactive troubleshooting decision trees to customer-facing portals.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Decision-tree DAG cycle, unreachable node, and broken transition reference blocker; Simpson's paradox separation preventing aggregate CSAT averages from hiding enterprise churn signals; Absent ARR/renewal date null preservation (never coercing unknown ARR to zero).
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Hourly VIP Escalation Radar" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly VIP escalation exposure check via scripts/escalation_exposure_scorer.py across open Sev1/Sev2 accounts and renewal windows.""*

## Example Queries & Verified Outcomes

- **`critical-escalation-warroom`** ([skill guide](skills/critical-escalation-warroom/README.md)): Connector prompt: *"Score Stratos Telecom escalation ($650k ARR, renewal in 45 days, 2 Sev1 cases, competitor threat) across CRM and CSM."* Verified starter check against `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` (`131.3 ms`): `escalations_scored=3`, `war_room_count=2`, `arr_at_war_room_risk_usd=2270000.0`, `total_escalated_arr_usd=2580000.0`.
- **`csat-churn-signal-miner`** ([skill guide](skills/csat-churn-signal-miner/README.md)): Connector prompt: *"Analyze Veloce SuperApp CSAT responses where 2 of 6 rows omitted csat_score."* Verified starter check against `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` (`132.9 ms`): `total_responses=3`, `rated_csat_count=3`, `unrated_csat_excluded=0`, `avg_csat=2.67`.
- **`troubleshooting-tree-author`** ([skill guide](skills/troubleshooting-tree-author/README.md)): Connector prompt: *"Validate our payment-timeout diagnostic tree JSON containing an infinite retry loop and a dangling branch target."* Verified starter check against `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` (`140.8 ms`): `node_count=4`, `root_node_id=N-START`, `graph_valid=False`, `broken_ref_count=0`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-14`** (`6 tabs, 4,411 rows (.xlsx) + 26-page .docx`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.868 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.925 / 1.000`) and `Prose-Only Baseline` (`FAIL 0.492 / 0.000`). Verified domain traps: Composite ARR x renewal proximity x Sev-1 war-room ranking; Blended CSAT 4.99 masking high-ARR detractor churn comments.
