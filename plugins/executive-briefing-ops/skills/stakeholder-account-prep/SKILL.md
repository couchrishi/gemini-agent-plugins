---
name: stakeholder-account-prep
description: "Aggregates commercial ARR milestones, renewal countdowns, open P1/P2 escalations, and executive touchpoints into scored stakeholder prep dossiers. Use when prepping for customer QBRs or executive sponsor calls. Don't use for deal discount approvals (use deal-desk-quote-guard)."
created_by: gemini-agent-plugins
---

# Stakeholder Account Prep

Assemble executive-ready stakeholder briefings combining commercial milestones, renewal timelines, open support escalations, NPS scores, and touchpoint freshness with strict data-completeness guards.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `salesforce_soql_api`, `google_calendar_api`, `gmail_api` | Query CRM account milestones, open escalations, and recent exec email/calendar touchpoints (checking SOQL `done` and `nextRecordsUrl`). |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Drive`, `Gmail`, `Google Calendar` | Read Account Health Sheets (`UNFORMATTED_VALUE`) and recent customer meeting notes in Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load uploaded account health JSON/CSV extracts via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Read [config.json](references/config.json) via `view_file`.
2. Whenever `org_configured` is `false`, apply [deal-desk-approval-baseline.md](references/baselines/deal-desk-approval-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md), and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [dossier_synthesizer.py](scripts/dossier_synthesizer.py) in `pyrepl` and optionally visualize account health scorecards via `emit_a2ui`:

```python
from scripts.dossier_synthesizer import analyze, render_markdown

res = analyze("account_signals.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/dossier_synthesizer.py --input account_signals.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [salesforce-crm-soql-traps.md](references/traps/salesforce-crm-soql-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Treat missing escalation or CRM feeds as `UNVERIFIED_INSUFFICIENT_SCOPE`, never assuming 0 open escalations.
- Creating private prep Docs is auto-allowed; emailing external customer contacts or modifying CRM opportunity fields requires explicit user confirmation (HITL).
