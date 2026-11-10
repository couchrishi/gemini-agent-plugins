---
name: pnl-budget-variance-bridge
description: "Computes P&L Actual vs Budget and Forecast variance bridges decomposed into constant-FX volume/rate vs FX translation impact, enforces leaf-vs-parent GL hierarchy tie-outs to prevent double-counting, and flags materiality breaches. Use when preparing monthly close commentary or CFO variance decks. Don't use for vendor invoice 3-way matching (use ap-three-way-match)."
created_by: gemini-agent-plugins
---

# P&L Budget Variance Bridge

Calculate exact constant-currency vs FX P&L variance bridges across hierarchical GL accounts without summary-row double-counting.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api`, `sap_odata_api` | Query GL actuals, budget versions, and period-end exchange rates from BigQuery/ERP marts. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Docs`, `Google Drive` | Extract close workbooks via Sheets `UNFORMATTED_VALUE` and commentary Docs in Finance Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Read uploaded GL trial-balance extracts directly into Python RAM using `view_file`. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [pnl_variance_engine.py](scripts/pnl_variance_engine.py) inside persistent `pyrepl` and optionally visualize bridges with `emit_a2ui`:

```python
from scripts.pnl_variance_engine import analyze, render_markdown

res = analyze("gl_variance.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/pnl_variance_engine.py --input gl_variance.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Always separate `row_type == "summary"` parent rows from leaf rows before summing EBITDA so totals are never doubled.
- Publishing executive close memos or adjusting ERP forecast/journal entries requires explicit user confirmation (HITL).
