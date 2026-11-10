---
name: supplier-otif-chargeback-auditor
description: "Calculates vendor PO On-Time In-Full scores with buyer/weather exclusions, computes contractual late and short-ship chargebacks, and reconciles live-unload detention eligibility Use when generating vendor delivery scorecards or reconciling supplier chargeback vs carrier detention claims. Don't use for auditing store shrink (use store-ops-shrink-copilot)."
created_by: gemini-agent-plugins
---

# Supplier OTIF, Chargebacks & Detention Auditor

Apply exact contractual grace windows, fill-rate tolerances, and detention forfeit rules to eliminate disputes over vendor compliance debits.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api, bigquery_sql_api` | Pull PO scheduled appointments, gate arrival timestamps, and GR quantities from SAP/WMS feeds. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read DC Dock Receipt & Carrier Detention Logs in Supply Chain Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load dock arrival JSON payloads in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [otif_detention_calculator.py](scripts/otif_detention_calculator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.otif_detention_calculator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/otif_detention_calculator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md).
- Enforce routing-guide rule: late-arriving carriers (`on_time == false`) forfeit free-time detention claims while verified `WEATHER_FORCE_MAJEURE` waives late chargebacks.
- Issuing formal AP debit memos or approving carrier detention invoices requires Supply Chain Vendor Ops sign-off (HITL).
