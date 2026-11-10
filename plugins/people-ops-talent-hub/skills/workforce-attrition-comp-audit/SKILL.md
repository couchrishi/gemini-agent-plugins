---
name: workforce-attrition-comp-audit
description: "Audits Workday compensation bands and departmental attrition after deduplicating effective-dated rows, separating contractors, normalizing pay frequencies, and suppressing small cells under n=5 Use when analyzing compa-ratios, pay compression, or workforce attrition metrics. Don't use for reviewing single-candidate interview scorecards (use structured-hiring-rubric)."
created_by: gemini-agent-plugins
---

# Workforce Attrition & Compa-Ratio Audit

Eliminate effective-dated snapshot duplication, contractor contamination, and small-cell privacy leaks before publishing HR metrics.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `workday_raas_api` | Pull Workday effective-dated compensation snapshots, job level bands, and FX tables. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Compensation Audit Sheets (`UNFORMATTED_VALUE`) in Finance/People Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse uploaded Workday CSV/JSON worker extracts directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [hr-hiring-comp-baseline.md](references/baselines/hr-hiring-comp-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [comp_band_analyzer.py](scripts/comp_band_analyzer.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.comp_band_analyzer import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/comp_band_analyzer.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [workday-hris-traps.md](references/traps/workday-hris-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Always collapse multiple `effective_date` rows per `worker_id` (<= as_of_date), exclude future rows, isolate CWKs, normalize HOURLY*2080 / MONTHLY*12, and redact cells where FTE < 5.
- Submitting base pay or merit adjustments into Workday requires explicit Compensation Lead approval (HITL).
