---
name: incident-triage-routing
description: "Triages active ServiceNow and Jira incidents using business-elapsed SLA burn, clusters correlated CI/error storms, and ranks matching runbooks. Use when prioritizing P1/P2 queues or investigating incident spikes. Don't use for scoring CAB change requests (use change-risk-cab-review)."
created_by: gemini-agent-plugins
---

# Incident Triage & Routing

Prioritize open ServiceNow and Jira incidents using business-elapsed SLA budgets rather than wall-clock timestamps, cluster emerging infrastructure storms by CI and error signature, and rank runbooks.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_table_api`, `jira_service_management_api`, `atlassian_confluence_cloud` | Query incidents with `sysparm_display_value=all`, inspect `X-Total-Count`, and fetch `task_sla.business_elapsed_minutes`. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Drive`, `Google Docs` | Read exported Incident Queue Sheets and Runbook Docs from SRE Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv`, `.md` | Load uploaded incident tables and runbook JSON/CSV files via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Read [config.json](references/config.json) using `view_file`.
2. Whenever `org_configured` is `false`, apply [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [sla_cluster_triage.py](scripts/sla_cluster_triage.py) in `pyrepl` (or schedule hourly via `schedule_task` and render triage queues with `emit_a2ui`):

```python
from scripts.sla_cluster_triage import analyze, render_markdown

res = analyze("incidents.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/sla_cluster_triage.py --input incidents.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Enforce [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Always exclude canceled tickets (`state=8`) from active counts and subtract `sla_paused_minutes` when `business_elapsed_minutes` is not pre-computed.
- Never reassign P1/P2 incidents or update tickets in bulk without explicit user confirmation (HITL).
