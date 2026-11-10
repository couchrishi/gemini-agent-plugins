---
name: pipeline-hygiene-slippage
description: "Audits Salesforce CRM opportunity pipelines for stage staleness, close-date slippage pushes, missing MEDDPICC commit gates, single-threading, and multi-currency FX traps. Use when running forecast hygiene reviews. Don't use for individual quote discount math (use deal-desk-quote-guard)."
created_by: gemini-agent-plugins
---

# Pipeline Hygiene & Slippage Auditor

Inspect live or exported Salesforce opportunity pipelines in RAM to catch multi-currency addition errors, stale stages, chronic close-date slippage, and under-threaded Commit deals.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `salesforce_soql_api` | Query open opportunities (`IsClosed = false`), `DatedConversionRate`, and `OpportunityHistory` following `nextRecordsUrl` until `done = true`. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Drive` | Read weekly Pipeline Export Sheets and FX Rate Tables (`UNFORMATTED_VALUE`) in Revenue Ops Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load uploaded CRM opportunity and FX rate JSON/CSV files via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [deal-desk-approval-baseline.md](references/baselines/deal-desk-approval-baseline.md) and [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md), and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [pipeline_slippage_auditor.py](scripts/pipeline_slippage_auditor.py) in `pyrepl` (or schedule weekly audits via `schedule_task` and visualize risk coverage via `emit_a2ui`):

```python
from scripts.pipeline_slippage_auditor import analyze, render_markdown

res = analyze("pipeline.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/pipeline_slippage_auditor.py --input pipeline.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [salesforce-crm-soql-traps.md](references/traps/salesforce-crm-soql-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Never sum nominal `JPY`, `EUR`, and `USD` deal amounts without normalizing via `fx_rates`.
- Modifying CRM forecast categories or pushing close dates requires explicit user confirmation (HITL).
