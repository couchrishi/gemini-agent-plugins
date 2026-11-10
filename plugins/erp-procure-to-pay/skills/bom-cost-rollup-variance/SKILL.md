---
name: bom-cost-rollup-variance
description: "Explodes multi-level Bills of Materials with scrap yield multipliers, detects cyclic references, and decomposes finished-good Purchase Price Variance down to leaf components Use when rolling up product standard vs actual BOM costs or isolating component inflation drivers. Don't use for clearing GR/IR suspense lines (use gr-ir-clearing-orchestrator)."
created_by: gemini-agent-plugins
---

# Multi-Level BOM Cost Rollup & PPV Engine

Trace finished-good margin erosion down to exact purchased sub-components across multi-level BOM explosions.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api, bigquery_sql_api` | Pull multi-level BOM edges and material standard/actual cost tables from SAP/BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Indented BOM & Costing Workbooks (`UNFORMATTED_VALUE`) in Manufacturing Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load BOM graph & component cost JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [bom_ppv_rollup.py](scripts/bom_ppv_rollup.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.bom_ppv_rollup import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/bom_ppv_rollup.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Apply `1 + scrap_factor_pct / 100` at every assembly edge and detect cycles via DFS stack guard.
- Updating SAP material standard costs (CK24) requires Cost Accounting Lead approval (HITL).
