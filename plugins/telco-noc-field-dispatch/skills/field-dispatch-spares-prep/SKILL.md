---
name: field-dispatch-spares-prep
description: "Matches telecom field work orders against technician skills, climbing/high-voltage certification expiration dates, and depot spare parts availability prior to dispatch Use when preparing field engineer truck rolls or checking work-order dispatch readiness. Don't use for correlating SNMP outage graphs (use noc-outage-topology-correlator)."
created_by: gemini-agent-plugins
---

# Field Dispatch Cert & Spares Readiness

Stop wasted truck rolls caused by expired tower-climbing certifications or missing optical transceivers at the depot.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_table_api` | Query ServiceNow FSM work orders, technician skills/certs, and depot bin spare inventory. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Field Tech Cert Matrix & Depot Spares Sheets (`UNFORMATTED_VALUE`) in Field Ops Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load dispatch work order & depot JSON payloads in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [dispatch_readiness_matcher.py](scripts/dispatch_readiness_matcher.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.dispatch_readiness_matcher import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/dispatch_readiness_matcher.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md).
- Compare every required safety cert expiry strictly against `dispatch_date`; reject expired certs even when skill tags match.
- Releasing field truck rolls and depot parts pick-tickets requires Dispatch Coordinator approval (HITL).
