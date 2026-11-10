---
name: problem-rca-kb-generator
description: "Groups repeat resolved incidents into Problem candidates, calculates mean/p90 MTTR and annualized L1 deflection savings, and validates KCS KB completeness. Use when reducing repeat tickets or drafting KCS articles. Don't use for real-time P1 triage (use incident-triage-routing)."
created_by: gemini-agent-plugins
---

# Problem RCA & KCS Deflection Generator

Mine historical incident exports to surface high-ROI Problem management candidates, calculate true MTTR excluding open and canceled noise, and validate draft Knowledge-Centered Service (KCS) articles.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_table_api`, `jira_service_management_api`, `atlassian_confluence_cloud` | Paginate closed/resolved tickets (`state in [6, 7]`), preserving exact `X-Total-Count` and excluding unresolved rows from MTTR. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Docs`, `Google Drive` | Read historical Ticket Dump Sheets and draft KCS Google Docs inside Service Desk Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv`, `.md` | Load uploaded historical ticket JSON/CSV datasets and draft KCS payloads in Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [kcs_deflection_analyzer.py](scripts/kcs_deflection_analyzer.py) in `pyrepl` and optionally emit ROI charts with `emit_a2ui`:

```python
from scripts.kcs_deflection_analyzer import analyze, render_markdown

res = analyze("resolved_tickets.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/kcs_deflection_analyzer.py --input resolved_tickets.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Never assign `0h` MTTR to tickets with `resolved_at: null`; exclude open and canceled tickets from closed MTTR averages and count them separately.
- Drafting KCS articles locally is auto-allowed; publishing articles to external self-service portals requires explicit user confirmation (HITL).
