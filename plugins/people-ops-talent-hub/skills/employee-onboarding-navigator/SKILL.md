---
name: employee-onboarding-navigator
description: "Builds 30/60/90-day onboarding checklists and identifies overdue provisioning, missing Day-1 gates, and blocked task dependencies Use when tracking new-hire readiness or auditing stalled IT/HR onboarding tasks. Don't use for calibrating candidate interviews (use structured-hiring-rubric)."
created_by: gemini-agent-plugins
---

# Employee Onboarding 30/60/90 Navigator

Verify Day-1 SSO/laptop/security readiness and track 30/60/90 milestones without assuming missing tasks are complete.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_hrsd_api, workday_raas_api` | Pull hire start dates and HRSD/IT provisioning tasks from Workday and ServiceNow. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Gmail, Google Drive` | Read Onboarding Tracker Sheets (`UNFORMATTED_VALUE`) and IT setup threads in Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load new-hire task JSON extracts in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [hr-hiring-comp-baseline.md](references/baselines/hr-hiring-comp-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [onboarding_plan_builder.py](scripts/onboarding_plan_builder.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.onboarding_plan_builder import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/onboarding_plan_builder.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [workday-hris-traps.md](references/traps/workday-hris-traps.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Missing mandatory Day-1 tasks MUST produce `AT_RISK_MISSING_DAY1_GATES` — never treat absent rows as finished.
- Triggering HRIS onboarding workflow overrides or external equipment escalations requires explicit confirmation (HITL).
