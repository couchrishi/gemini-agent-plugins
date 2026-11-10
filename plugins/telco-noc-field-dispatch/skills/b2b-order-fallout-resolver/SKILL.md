---
name: b2b-order-fallout-resolver
description: "Classifies B2B telecom provisioning fallout orders into credit, address, LNP port, OSP fiber capacity, or CPE queues while prioritizing by SLA breach and MRC at risk Use when triaging enterprise fiber/MPLS/SIP order backlogs or quantifying delayed ARR. Don't use for correlating live NOC outage alarms (use noc-outage-topology-correlator)."
created_by: gemini-agent-plugins
---

# B2B Telecom Order Fallout & MRC Classifier

Unblock delayed enterprise recurring revenue by routing provisioning fallout exceptions to the exact operational team.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api, servicenow_table_api` | Pull B2B OSS/BSS fallout queues, error codes, and contracted MRC values from BigQuery or ServiceNow. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read B2B Provisioning Fallout & Backlog Sheets in Enterprise Delivery Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse order fallout JSON queues in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [order_fallout_classifier.py](scripts/order_fallout_classifier.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.order_fallout_classifier import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/order_fallout_classifier.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md).
- Rank queues by `sla_breached` first and `mrc_usd` second so high-value delayed circuits get immediate engineering unblock.
- Waiving credit holds or escalating carrier construction permits requires B2B Delivery Lead confirmation (HITL).
