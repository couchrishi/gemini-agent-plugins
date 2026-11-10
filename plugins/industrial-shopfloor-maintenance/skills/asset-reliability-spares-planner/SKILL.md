---
name: asset-reliability-spares-planner
description: "Computes asset MTBF (including conservative zero-failure censoring), lead-time spare demand, safety stock, Reorder Points, and stockout expedite recommendations Use when optimizing plant MRO spare-parts min/max levels or preventing line-down stockouts. Don't use for auditing confined-space EHS work permits (use ehs-safety-permit-auditor)."
created_by: gemini-agent-plugins
---

# Asset Reliability & Critical Spares ROP Planner

Prevent catastrophic plant downtime by sizing MRO safety stock deterministically from fleet operating hours and lead times.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api, bigquery_sql_api` | Pull SAP PM equipment hours, failure work orders, and MM stock/open POs. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Plant Critical Spares & Failure History Sheets (`UNFORMATTED_VALUE`) in Manufacturing Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load spares inventory & failure history JSONs in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [mtbf_spares_optimizer.py](scripts/mtbf_spares_optimizer.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.mtbf_spares_optimizer import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/mtbf_spares_optimizer.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md).
- When `observed_failures == 0`, apply conservative right-censored estimator (`0.5` pseudo-failures) instead of dividing by zero or claiming infinite MTBF.
- Submitting MRO purchase requisitions to SAP MM requires Maintenance Manager sign-off (HITL).
