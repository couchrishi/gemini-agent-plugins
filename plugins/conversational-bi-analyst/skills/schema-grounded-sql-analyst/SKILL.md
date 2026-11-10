---
name: schema-grounded-sql-analyst
description: "Validates analytical SQL against table metadata for missing partition filters, M:N join fanouts, destructive DDL/DML, and metric denominator mismatches before execution. Use when authoring or auditing BigQuery/Snowflake queries. Don't use for segment variance bridges (use kpi-anomaly-driver-tree)."
created_by: gemini-agent-plugins
---

# Schema-Grounded SQL Analyst

Inspect every analytical SQL query against table partition metadata, primary key constraints, and denominator alignment rules before running against BigQuery, Snowflake, or Looker.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_api`, `snowflake_sql_api`, `looker_api` | Fetch INFORMATION_SCHEMA table definitions, partition keys, and dry-run scan estimates before executing SELECT queries. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Drive` | Read Connected Sheets SQL specs and Data Dictionary Sheets from BI Shared Drives. |
| **Mode C — Direct File Upload** | `.sql`, `.json`, `.csv` | Parse uploaded SQL files and schema JSON metadata via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Read [config.json](references/config.json) using `view_file`.
2. Whenever `org_configured` is `false`, apply [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [sql_safety_and_fanout_checker.py](scripts/sql_safety_and_fanout_checker.py) in `pyrepl` before executing warehouse SQL:

```python
from scripts.sql_safety_and_fanout_checker import analyze, render_markdown

res = analyze("query_and_schema.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/sql_safety_and_fanout_checker.py --input query_and_schema.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), and [google-workspace-traps.md](references/traps/google-workspace-traps.md).
- Never execute queries lacking required partition filters or containing unresolved M:N join fanouts (`SUM` over ungrouped multi-row child joins).
- Read-only dry-run checks are auto-allowed; running high-scan queries above `max_query_scan_gb` or any DDL/DML requires explicit user confirmation (HITL).
