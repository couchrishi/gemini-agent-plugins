# Telecom NOC & Field Network Dispatch (`telco-noc-field-dispatch`)

Suppresses downstream network alarm storms via parent-child topology graph correlation, validates technician climbing/safety certifications and van/depot spares prior to field dispatch, and classifies B2B enterprise provisioning order fallout by queue and MRC-at-risk. Pairs live `/work` connectors (`ServiceNow, BigQuery, Postgres, Google Drive, Google Sheets, Google Docs`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Network Operations Center (NOC) Duty Lead | Isolating root optical fiber or core router faults during multi-thousand alarm storms | [`noc-outage-topology-correlator`](skills/noc-outage-topology-correlator/README.md) | `scripts/alarm_topology_correlator.py` |
| Field Dispatch & Workforce Scheduler | Assigning certified RF/fiber field technicians and reserved spares kits to morning work orders | [`field-dispatch-spares-prep`](skills/field-dispatch-spares-prep/README.md) | `scripts/dispatch_readiness_matcher.py` |
| Enterprise Carrier Provisioning Manager | Triaging stalled B2B fiber, DIA, and SD-WAN orders past the `15`-day provisioning SLA | [`b2b-order-fallout-resolver`](skills/b2b-order-fallout-resolver/README.md) | `scripts/order_fallout_classifier.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`telco-noc-field-dispatch.zip`](../../dist/bundles/telco-noc-field-dispatch.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/noc-outage-topology-correlator.zip`](../../dist/skills/noc-outage-topology-correlator.zip) — Traces upstream parent-child network graphs to suppress downstream alarm storms and roll up impacted subscribers and VIP circuits.
  - [`dist/skills/field-dispatch-spares-prep.zip`](../../dist/skills/field-dispatch-spares-prep.zip) — Validates technician skills and non-expired safety certs as of dispatch date alongside depot/van spare kit stock before truck rolls.
  - [`dist/skills/b2b-order-fallout-resolver.zip`](../../dist/skills/b2b-order-fallout-resolver.zip) — Classifies stuck B2B DIA/MPLS/SIP orders into deterministic remediation queues and quantifies Monthly Recurring Charge (MRC) at risk.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`telco-noc-field-dispatch.zip`](../../dist/bundles/telco-noc-field-dispatch.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/telco-noc-field-dispatch` / `@telco-noc-field-dispatch` so Layer 1 (`remote_cli mcp`) pulls live data from `ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs` or `NMS Alarm Topology & Field Service Dispatch MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` (`5,870 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Telco_NOC_Alarm_Stream`, `Topology_Node_Inventory`, `Topology_Links_Edges`, `Dispatch_Work_Orders`, `Field_Technicians`, `Depot_Spare_Stock`, `B2B_Order_Fallout_Ledger`)](../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx):

```bash
python3 plugins/telco-noc-field-dispatch/skills/noc-outage-topology-correlator/scripts/alarm_topology_correlator.py \
  --input examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx \
  --config plugins/telco-noc-field-dispatch/skills/noc-outage-topology-correlator/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `ServiceNow`, `BigQuery`, `Postgres`, `Google Drive`, `Google Sheets`, `Google Docs`.
- **Customer BYO-MCP Servers**: `NMS Alarm Topology & Field Service Dispatch MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Fetch live network alarm graphs, technician safety certifications, depot spare inventory, and B2B provisioning fallout orders from ServiceNow, BigQuery, Postgres, or customer NMS/Dispatch MCP servers via remote_cli mcp before Python BFS and readiness checks.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` (`5,870 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Telco_NOC_Alarm_Stream`, `Topology_Node_Inventory`, `Topology_Links_Edges`, `Dispatch_Work_Orders`, `Field_Technicians`, `Depot_Spare_Stock`, `B2B_Order_Fallout_Ledger`)](../../examples/telco-noc-field-dispatch/Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md), [`finance-materiality-baseline.md`](../../shared/baselines/finance-materiality-baseline.md) and [`servicenow-jira-itsm-traps.md`](../../shared/traps/servicenow-jira-itsm-traps.md), [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md), [`bigquery-sap-erp-traps.md`](../../shared/traps/bigquery-sap-erp-traps.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Dispatching field truck rolls and reserving depot spares in customer Field Service MCP; Bulk-closing or linking correlated child alarms in ServiceNow / NMS MCP.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Visited-set BFS optical ring correlation preventing infinite topology loops while deduplicating downstream child alarms; Hard dispatch block whenever tower-climb/electrical safety certs are expired or required depot spares are unavailable; Revenue-weighted MRC escalation prioritization on aged B2B order fallout.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Hourly B2B Provisioning Fallout Watch" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly B2B provisioning fallout sweep via scripts/order_fallout_classifier.py and highlight P1 executive escalations where aged MRC breaches SLA.""*

## Example Queries & Verified Outcomes

- **`noc-outage-topology-correlator`** ([skill guide](skills/noc-outage-topology-correlator/README.md)): Connector prompt: *"Correlate Stratos Telecom alarm flood with 1 metro agg router alarm feeding 18 alarming 5G gNodeBs serving 12,400 subscribers."* Verified starter check against `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` (`150.3 ms`): `raw_alarms_ingested=4`, `correlated_root_incidents=1`, `symptom_alarms_suppressed=3`, `noise_reduction_pct=75.0`.
- **`field-dispatch-spares-prep`** ([skill guide](skills/field-dispatch-spares-prep/README.md)): Connector prompt: *"Prepare dispatch for Stratos Telecom WO-88 with only one fiber tech whose climbing cert expired yesterday."* Verified starter check against `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` (`143.0 ms`): `dispatch_date=2026-11-10`, `work_orders_checked=2`, `ready_count=1`, `blocked_count=1`.
- **`b2b-order-fallout-resolver`** ([skill guide](skills/b2b-order-fallout-resolver/README.md)): Connector prompt: *"Triage Stratos Telecom B2B fallout queue with aged $4,200/mo DIA circuit hitting OLT port capacity and $1,100/mo SIP LNP freeze."* Verified starter check against `Apex_Telco_NOC_Topology_Dispatch_and_Fallout_Sample.xlsx` (`141.2 ms`): `orders_in_fallout=2`, `sla_breached_count=2`, `total_mrc_at_risk_usd=13600.0`, `annualized_arr_blocked_usd=163200.0`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-19`** (`7 tabs, 5,309 rows (.xlsx) + 24-page Runbook PDF`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.861 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.860 / 1.000`) and `Prose-Only Baseline` (`PASS 0.887 / 1.000`). Verified domain traps: Cyclic ring topology BFS without infinite recursion (75% alarm suppression); Expired tower-climb certification dispatch block (Samir Patel); MRC x aged-day B2B fallout prioritization.
