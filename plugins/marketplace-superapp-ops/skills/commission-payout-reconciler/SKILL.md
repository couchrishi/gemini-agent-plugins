---
name: commission-payout-reconciler
description: "Reconciles merchant gross GMV, marketplace commission fees, PSP processing charges, promo co-funding, refunds, FX conversion, and bank settlement wires Use when closing daily merchant payout runs or investigating PSP settlement variances. Don't use for resolving delivery courier latency disputes (use logistics-sla-dispute-resolver)."
created_by: gemini-agent-plugins
---

# Commission, FX & Merchant Payout Reconciler

Guarantee penny-exact merchant payout reconciliation before releasing bank settlement batches.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api, rest_webhook_api` | Query BigQuery order ledger summaries alongside PSP payout batch settlement reports. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Merchant Settlement & FX Conversion Sheets (`UNFORMATTED_VALUE`) in Marketplace Finance Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load merchant settlement JSON payloads in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [payout_ledger_reconciler.py](scripts/payout_ledger_reconciler.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.payout_ledger_reconciler import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/payout_ledger_reconciler.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md).
- Apply commission % and processing fee % to `gross_gmv_local` BEFORE FX conversion (`fx_rate_to_settlement`) to prevent currency cross-rate drift.
- Releasing PSP merchant payout transfers or initiating negative-balance clawback debits requires Marketplace Finance Controller approval (HITL).
