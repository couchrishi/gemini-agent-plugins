---
name: change-risk-cab-review
description: "Scores ServiceNow and Jira Change Requests on a 0-100 CAB rubric covering blast radius, tested rollback, freeze-window collisions, and CI failure history. Use when preparing weekly Change Advisory Board reviews. Don't use for incident SLA triage (use incident-triage-routing)."
created_by: gemini-agent-plugins
---

# Change Risk & CAB Review

Evaluate pending production Change Requests against deterministic blast-radius, rollback-validation, freeze-window, CI failure history, and staging/canary coverage rules before CAB sign-off.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_table_api`, `jira_service_management_api` | Pull pending `change_request` rows (`sysparm_display_value=all`), CMDB CI tier metadata, and blackout freeze calendars. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Drive`, `Google Docs` | Read Change Queue Sheets (`UNFORMATTED_VALUE`) and CAB Freeze Calendar Sheets in IT Ops Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load uploaded change request and freeze window JSON/CSV files via `view_file` in Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Run [cab_risk_scorer.py](scripts/cab_risk_scorer.py) in `pyrepl` and optionally visualize risk breakdowns with `emit_a2ui`:

```python
from scripts.cab_risk_scorer import analyze, render_markdown

res = analyze("changes.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/cab_risk_scorer.py --input changes.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Apply [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Treat missing rollback evidence or unverified CMDB history as risk points rather than assuming zero risk.
- Approving or rejecting CAB change tickets (`risk_score >= 30` or colliding with a freeze window) requires explicit human CAB confirmation (HITL).
