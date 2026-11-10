---
name: meeting-to-execution-pack
description: "Transforms meeting transcripts and raw notes into owner-assigned commitments, decision logs, unresolved blockers, and repeat carryover trackers. Use when turning Meet/Teams transcripts into execution packs. Don't use for building morning calendar prep briefs (use daily-executive-briefing)."
created_by: gemini-agent-plugins
---

# Meeting to Execution Pack

Convert raw meeting transcripts and structured notes into clean owner-assigned action items, formal decision logs, unresolved blockers, and carryover alerts across prior sessions.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_calendar_api`, `gmail_api`, `microsoft_graph_calendar_mail` | Fetch linked Google Meet or Teams transcript Docs and reconcile against the prior session's open action tracker. |
| **Mode B — Google Workspace Fallback** | `Google Meet`, `Google Docs`, `Google Drive` | Read all tabs of the meeting notes Google Doc (`includeTabsContent`) and any linked Drive tracker Sheet. |
| **Mode C — Direct File Upload** | `.json`, `.md`, `.txt`, `.csv` | Parse uploaded transcript text or JSON speaker segments via `view_file` inside Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Read [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [deal-desk-approval-baseline.md](references/baselines/deal-desk-approval-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md), and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [transcript_action_extractor.py](scripts/transcript_action_extractor.py) in `pyrepl` and optionally display action summaries with `emit_a2ui`:

```python
from scripts.transcript_action_extractor import analyze, render_markdown

res = analyze("meeting_transcript.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/transcript_action_extractor.py --input meeting_transcript.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Apply [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [salesforce-crm-soql-traps.md](references/traps/salesforce-crm-soql-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Flag `UNASSIGNED` actions and unattributed transcripts explicitly instead of guessing ownership.
- Creating private Doc summaries or email drafts is auto-allowed; emailing external attendees or posting to shared Slack/Chat channels requires explicit user confirmation (HITL).
