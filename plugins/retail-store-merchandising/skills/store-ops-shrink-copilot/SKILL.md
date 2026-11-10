---
name: store-ops-shrink-copilot
description: "Quantifies store shrink variance, detects zero-scan phantom inventory and negative inventory corruption while filtering out unpolled POS terminals, and prioritizes associate tasks Use when running daily store inventory audits, loss-prevention reviews, or shelf replenishment workflows. Don't use for computing vendor dock OTIF chargebacks (use supplier-otif-chargeback-auditor)."
created_by: gemini-agent-plugins
---

# Store Shrink, Phantom Inventory & Associate Tasks

Turn noisy perpetual inventory and POS scan telemetry into actionable, dollar-ranked store associate floor tasks.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api, sap_odata_api` | Query BigQuery daily POS scan aggregates paired with SAP perpetual stock balances. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Store Cycle-Count & On-Hand Variance Sheets (`UNFORMATTED_VALUE`) in Retail Store Ops Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load SKU/store inventory snapshot JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [store_shrink_task_ranker.py](scripts/store_shrink_task_ranker.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.store_shrink_task_ranker import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/store_shrink_task_ranker.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md).
- Enforce `pos_poll_status == 'POLLED'` before flagging `PHANTOM_INVENTORY_ZERO_SCAN` so offline registers do not look like empty shelves.
- Posting physical shrink write-offs to GL COGS requires Store Director or Regional Loss Prevention sign-off (HITL).
