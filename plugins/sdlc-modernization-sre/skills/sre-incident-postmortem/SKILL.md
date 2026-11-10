---
name: sre-incident-postmortem
description: "Computes exact TTD, TTM, and TTR incident intervals, 30-day SLO error-budget burn rates, availability impact, and corrective-action SLA status. Use when writing blameless postmortems or reviewing weekly SLO health. Don't use for real-time alert triage (use incident-triage-routing)."
created_by: gemini-agent-plugins
---

# SRE Incident Postmortem & SLO Calculator

Calculate exact incident detection/mitigation/resolution intervals, weighted error-budget burn rates, and corrective-action SLA compliance in Python RAM for blameless postmortems.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `cloud_logging_api`, `jira_api` | Query incident timeline timestamps (`started_at`, `detected_at`, `mitigated_at`, `resolved_at`) and linked postmortem Jira action items. |
| **Mode B — Google Workspace Fallback** | `Google Docs`, `Google Sheets` | Read Postmortem Docs (`includeTabsContent`) and SRE Action Tracker Sheets from Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv`, `.md` | Load uploaded incident timeline and action-item JSON payloads via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [slo_timeline_calculator.py](scripts/slo_timeline_calculator.py) in `pyrepl` (or schedule weekly SLO reviews via `schedule_task` and render burn charts with `emit_a2ui`):

```python
from scripts.slo_timeline_calculator import analyze, render_markdown

res = analyze("postmortem_timeline.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/slo_timeline_calculator.py --input postmortem_timeline.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Flag open action items lacking due dates as `MISSING_DUE_DATE` instead of treating them as compliant.
- Drafting private postmortem Docs is auto-allowed; creating bulk Jira tickets or closing postmortems requires explicit user confirmation (HITL).
