---
name: kpi-anomaly-driver-tree
description: "Computes zero-residual Volume-Mix-Rate KPI bridges and z-score segment anomalies across period-over-period tables in RAM. Use when explaining revenue, margin, or volume swings. Don't use for SQL join-fanout checks (use schema-grounded-sql-analyst)."
created_by: gemini-agent-plugins
---

# KPI Anomaly & Driver Tree

Decompose period-over-period KPI movements deterministically into Volume, Mix, and Rate effects with zero residual, and surface statistically anomalous segments with small-sample protection.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_api`, `snowflake_sql_api`, `looker_api` | Pull pre-aggregated segment volume and revenue tables using verified partition filters and matching fiscal calendars. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Drive` | Read Connected Sheets KPI tabs (`UNFORMATTED_VALUE`) from Finance/BI Shared Drives. |
| **Mode C — Direct File Upload** | `.csv`, `.json` | Load uploaded segment performance tables directly via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [mix_rate_volume_bridge.py](scripts/mix_rate_volume_bridge.py) in `pyrepl` (or schedule daily checks via `schedule_task` and render bridge waterfalls with `emit_a2ui`):

```python
from scripts.mix_rate_volume_bridge import analyze, render_markdown

res = analyze("kpi_segments.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/mix_rate_volume_bridge.py --input kpi_segments.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), and [google-workspace-traps.md](references/traps/google-workspace-traps.md).
- Verify `bridge_residual == 0.0` and surface `low_sample_caution` whenever segment volume `< min_sample_size_guard`.
- Distributing executive KPI alerts externally or to broad leadership mailing lists requires explicit user confirmation (HITL).
