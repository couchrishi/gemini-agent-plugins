---
name: gr-ir-clearing-orchestrator
description: "Reconciles goods receipt vs invoice receipt clearing imbalances across SAP PO lines with TCURX decimal normalization, SHKZG reversals, and aging threshold flags Use when clearing SAP GR/IR suspense accounts or investigating open purchase order accruals. Don't use for comparing competing vendor RFx bids (use supplier-rfx-tariff-modeler)."
created_by: gemini-agent-plugins
---

# GR/IR Clearing Orchestrator

Identify GR-without-IR accruals, IR-without-GR overbillings, and stale >60d imbalances deterministically before SAP MR11 clearing.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api, bigquery_sql_api` | Pull SAP EKBE goods receipt (WE) and invoice receipt (RE) history rows. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read GR/IR Clearing Open Items Sheets (`UNFORMATTED_VALUE`) in Supply Chain Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load GR/IR postings JSON exports in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [gr_ir_reconciler.py](scripts/gr_ir_reconciler.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.gr_ir_reconciler import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/gr_ir_reconciler.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Scale `TCURX` zero-decimal currencies and negate `SHKZG='H'` lines; never mark `IR_WITHOUT_GR` lines eligible for payment.
- Posting MR11/F.13 clearing journals in SAP requires explicit Controller confirmation (HITL).
