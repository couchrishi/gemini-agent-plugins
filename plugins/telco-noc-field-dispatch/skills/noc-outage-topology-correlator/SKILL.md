---
name: noc-outage-topology-correlator
description: "Correlates telco SNMP/gNMI alarm storms across parent-child core, metro, OLT, and cell-site topology graphs to isolate root-cause nodes and roll up impacted subscribers Use when triaging multi-node telecom outage alarm floods or declaring P1/P2 NOC incidents. Don't use for matching technician safety certs for truck rolls (use field-dispatch-spares-prep)."
created_by: gemini-agent-plugins
---

# NOC Outage Topology Alarm Correlator

Cut through thousands of downstream ONT and cell-sector alarms to pinpoint the single upstream fiber or core router failure.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_table_api, bigquery_sql_api` | Pull active ServiceNow EM alerts (`em_alert` with display values) and network graph topology edges. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read NOC Active Alarm & Topology Edge Sheets in Network Reliability Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load topology + alarm JSON snapshots in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [alarm_topology_correlator.py](scripts/alarm_topology_correlator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.alarm_topology_correlator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/alarm_topology_correlator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md).
- Use cycle-safe BFS traversal over parent-child links so ring/mesh topologies never cause infinite alarm correlation loops.
- Declaring major P1 outages or mass-closing child alerts requires Duty NOC Incident Commander confirmation (HITL).
