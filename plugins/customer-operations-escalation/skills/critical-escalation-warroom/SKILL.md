---
name: critical-escalation-warroom
description: "Quantifies customer escalation severity and churn exposure (0-100) combining open Sev1/Sev2 backlog, SLA breaches, ARR, renewal proximity, outage hours, and competitor threats Use when triaging VIP support escalations or convening executive customer recovery war-rooms. Don't use for mining broad CSAT survey verbatims (use csat-churn-signal-miner)."
created_by: gemini-agent-plugins
---

# Critical Customer Escalation War-Room

Focus executive war-room engineering and TAM capacity on the highest-exposure renewals rather than loudest tickets.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `salesforce_soql_api, servicenow_csm_api` | Join Salesforce Account ARR/renewal dates with ServiceNow CSM open Sev1/Sev2 and SLA breach counts. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read VIP Account Health & Open Ticket Sheets (`UNFORMATTED_VALUE`) in Customer Ops Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse uploaded escalation JSON rosters in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [escalation_exposure_scorer.py](scripts/escalation_exposure_scorer.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.escalation_exposure_scorer import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/escalation_exposure_scorer.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [salesforce-crm-soql-traps.md](references/traps/salesforce-crm-soql-traps.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Align CRM Account IDs with ServiceNow Customer Accounts (avoid missing-ARR zeroing; report unmapped accounts explicitly).
- Activating formal exec war-room bridges or emailing VIP customers requires Support Director approval (HITL).
