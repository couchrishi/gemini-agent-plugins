---
name: supplier-rfx-tariff-modeler
description: "Computes total landed unit and annual cost across competing supplier RFx quotes under incremental tariff shock scenarios, working capital payment terms, and defect PPM risk Use when evaluating global sourcing bids or modeling country tariff sensitivity. Don't use for exploding internal bill-of-materials standard costs (use bom-cost-rollup-variance)."
created_by: gemini-agent-plugins
---

# Supplier RFx & Tariff Landed Cost Modeler

Rank global RFx suppliers on true Total Landed Cost rather than misleading headline FOB prices.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api, bigquery_sql_api` | Pull vendor quotes, customs duty tables, and quality PPM scores from ERP/BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read RFx Bid Matrix Sheets (`UNFORMATTED_VALUE`) in Strategic Sourcing Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load RFx bid JSON scenarios in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [landed_cost_simulator.py](scripts/landed_cost_simulator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.landed_cost_simulator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/landed_cost_simulator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Check `moq_feasible` and run `--tariff-shock-pct` sensitivity before recommending supplier switches.
- Awarding supplier contracts or issuing purchase orders requires explicit Procurement Lead confirmation (HITL).
