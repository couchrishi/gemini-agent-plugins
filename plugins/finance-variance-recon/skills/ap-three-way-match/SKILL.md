---
name: ap-three-way-match
description: "Performs deterministic PO/Goods Receipt/Invoice 3-way matching, normalizes SAP TCURX zero-decimal currencies and SHKZG credit signs, flags duplicate invoices and bank-change fraud alerts, and holds exceptions before ERP posting. Use when reconciling vendor invoices or AP payment runs. Don't use for customer collections aging (use ar-aging-collections-audit)."
created_by: gemini-agent-plugins
---

# AP Three-Way Match

Reconcile Purchase Orders, Goods Receipts, and Vendor Invoices deterministically in Python RAM before clearing AP batches for payment.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api`, `bigquery_sql_api` | Pull supplier invoices, PO line items, goods receipts, and `TCURR`/`TCURX` FX tables. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Gmail`, `Google Drive` | Read AP Invoice Register Sheets (`UNFORMATTED_VALUE`) and inspect remittance-change alerts in Gmail. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load uploaded PO/GR/Invoice exports directly into Python RAM using `view_file`. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [reconcile_3way.py](scripts/reconcile_3way.py) inside persistent `pyrepl` and optionally emit controller queue views via `emit_a2ui`:

```python
from scripts.reconcile_3way import analyze, render_markdown

res = analyze("ap_batch.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback (supports `--input` or separate `--po`/`--gr`/`--invoice` flags):

```bash
python3 scripts/reconcile_3way.py --input ap_batch.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Always scale zero-decimal (`JPY`, `KRW`) and 3-decimal (`KWD`, `BHD`) currencies per `TCURX`, flip `SHKZG='H'` credit rows, and block missing GRNs (`MISSING_GRN`).
- Posting ERP payments or modifying vendor bank accounts requires explicit user confirmation (HITL).
