---
name: executed-obligation-extractor
description: "Extracts renewal dates, calculates exact opt-out notice deadlines (renewal_date minus notice_days), detects uncapped CPI escalators, and compiles executed obligation calendars. Use when auditing signed agreements for renewal notices or recurring obligations. Don't use for negotiating unsigned contract drafts (use contract-playbook-redliner)."
created_by: gemini-agent-plugins
---

# Executed Obligation Extractor

Compute exact notice-window cutoffs, price-escalator exposures, and post-signature compliance deliverables from executed contracts.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api`, `microsoft_graph_sharepoint` | Retrieve executed PDF/Doc MSAs and signed order forms from Legal Repository folders. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Docs`, `Google Drive` | Read Executed Contract Registry Sheets (`UNFORMATTED_VALUE`) and Amendment Docs in Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse uploaded executed contract metadata directly in Python RAM using `view_file`. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [obligation_calendar_builder.py](scripts/obligation_calendar_builder.py) in `pyrepl` and optionally automate recurring sweeps with `schedule_task` or cards via `emit_a2ui`:

```python
from scripts.obligation_calendar_builder import analyze, render_markdown

res = analyze("executed_contracts.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/obligation_calendar_builder.py --input executed_contracts.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Any auto-renewing contract missing `notice_days` or `renewal_date` MUST be flagged `UNVERIFIED_MISSING_FIELDS` (never treat absent values as safe).
- Sending non-renewal notices to external vendors or triggering signature workflows requires explicit user confirmation (HITL).
