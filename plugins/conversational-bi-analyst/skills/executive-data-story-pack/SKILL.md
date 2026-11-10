---
name: executive-data-story-pack
description: "Profiles tabular CSV and JSON datasets in RAM for completeness, null rates, formula errors, IQR outliers, quantiles, and truncation ceilings, emitting verified A2UI Canvas chart payloads. Use when turning raw exports into executive data stories. Don't use for raw SQL validation (use schema-grounded-sql-analyst)."
created_by: gemini-agent-plugins
---

# Executive Data Story Pack

Profile multi-thousand-row datasets cleanly in Python RAM without dumping raw CSV rows into prompt tokens, guard against row-limit truncation and spreadsheet formula errors, and emit verified A2UI Canvas visualizations.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_api`, `snowflake_sql_api`, `looker_api` | Export query result sets with `total_available` row counts and explicit schema types. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Drive` | Read Workspace Sheets using `UNFORMATTED_VALUE` to preserve precision and detect `#N/A` / `#REF!` formula errors. |
| **Mode C — Direct File Upload** | `.csv`, `.json` | Profile uploaded datasets directly in RAM via `view_file` and Python without pasting full tables into context. |

## Org Configuration & Starter Baseline Rule

1. Read [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [dataset_profiler_guard.py](scripts/dataset_profiler_guard.py) in `pyrepl` and render `a2ui_chart_payload` via `emit_a2ui`:

```python
from scripts.dataset_profiler_guard import analyze, render_markdown

res = analyze("dataset.csv", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/dataset_profiler_guard.py --input dataset.csv --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Apply [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), and [google-workspace-traps.md](references/traps/google-workspace-traps.md).
- Never extrapolate totals when `truncated` is `true` or `row_limit_ceiling` is hit.
- Generating private Doc/Canvas packs is auto-allowed; sharing slide decks or emails broadly requires explicit user confirmation (HITL).
