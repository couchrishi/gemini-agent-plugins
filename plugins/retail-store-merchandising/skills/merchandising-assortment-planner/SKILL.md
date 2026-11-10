---
name: merchandising-assortment-planner
description: "Computes promotional unit and revenue lift normalized by campaign duration, adjusts for sibling SKU cannibalization, basket halo, and vendor coop funding, and calculates net margin ROI Use when evaluating retail promotion effectiveness, vendor co-op ROI, or seasonal markdown performance. Don't use for auditing store floor shrink variance (use store-ops-shrink-copilot)."
created_by: gemini-agent-plugins
---

# Merchandising Promo Lift & Margin ROI

Separate real incremental promotional profit from baseline sales shifted across time or cannibalized sibling SKUs.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api` | Pull BigQuery promotional basket attribution tables, coop funding credits, and baseline velocity windows. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Merchandising Promo Recap Sheets (`UNFORMATTED_VALUE`) in Category Management Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse promotion telemetry JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [promo_lift_analyzer.py](scripts/promo_lift_analyzer.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.promo_lift_analyzer import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/promo_lift_analyzer.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md).
- Normalize 28-day baseline totals to promo-day daily run rates BEFORE computing lift percentages (`chain-denominator-seams.md`).
- Locking promotional funding extensions or chain-wide markdown campaigns requires Category Merchant Director approval (HITL).
