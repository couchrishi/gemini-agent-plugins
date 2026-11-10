---
name: quality-capex-rca-copilot
description: "Quantifies manufacturing scrap defects into 80/20 cost Paretos, detects anomalous supplier lots exceeding 2x plant average, and evaluates engineering CapEx payback years Use when investigating plant scrap spikes or justifying quality CapEx requests. Don't use for calculating MRO spare-part reorder points (use asset-reliability-spares-planner)."
created_by: gemini-agent-plugins
---

# Quality Defect 80/20 Pareto & CapEx RCA

Pinpoint the vital few defect modes and suspect supplier lots driving scrap cost before funding engineering CapEx.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api, bigquery_sql_api` | Pull QMS non-conformance notifications, supplier batch lots, and scrap valuation logs from SAP QM/BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read Plant Quality Scrap Sheets and CapEx Business Case Docs in Manufacturing Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load scrap event & CapEx JSON payloads in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [defect_pareto_correlator.py](scripts/defect_pareto_correlator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.defect_pareto_correlator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/defect_pareto_correlator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md).
- Rank strictly by financial `scrap_cost_usd` (not just raw defect counts) so low-count high-cost assemblies stay visible.
- Quarantining supplier lots or approving CapEx expenditures requires Quality & Plant Finance sign-off (HITL).
