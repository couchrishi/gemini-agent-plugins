---
name: structured-hiring-rubric
description: "Calibrates structured interview scorecards across 1-4 anchors, flags score dispersion = 2.0, thin evidence, and potential bias phrasing Use when preparing hiring committee debriefs or auditing recruiter scorecards. Don't use for auditing compensation bands or employee attrition (use workforce-attrition-comp-audit)."
created_by: gemini-agent-plugins
---

# Structured Hiring Rubric Calibration

Audit panel scorecards before hiring debriefs so split opinions, thin behavioral notes, and bias proxies are resolved transparently.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `greenhouse_harvest_api` | Pull candidate interview scorecards and competency rubrics from Greenhouse. |
| **Mode B — Google Workspace Fallback** | `Google Docs, Google Sheets, Google Drive` | Read Interview Debrief Docs and Scorecard Tracker Sheets in Recruiting Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load candidate scorecard JSON exports in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [hr-hiring-comp-baseline.md](references/baselines/hr-hiring-comp-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [rubric_calibration_checker.py](scripts/rubric_calibration_checker.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.rubric_calibration_checker import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/rubric_calibration_checker.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [workday-hris-traps.md](references/traps/workday-hris-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Never average over a missing/invalid score or a Score 1 veto without forcing `DEBRIEF_REQUIRED_SPLIT_PANEL`.
- Advancing candidates to offer or rejecting applicants requires explicit Hiring Manager and Recruiter confirmation (HITL).
