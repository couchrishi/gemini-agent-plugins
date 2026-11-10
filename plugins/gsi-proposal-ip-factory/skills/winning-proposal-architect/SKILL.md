---
name: winning-proposal-architect
description: "Models GSI consulting staffing pyramids across delivery phases, calculates onshore/offshore leverage, blended bill rate, and gross margin against 30%/20% guardrails Use when pricing a consulting proposal or optimizing onshore/offshore staffing mix. Don't use for linting legal SOW scope creep clauses (use sow-scope-margin-auditor)."
created_by: gemini-agent-plugins
---

# Winning Proposal Staffing Pyramid Architect

Model phase-level delivery staffing pyramids and protect consulting gross margins deterministically in Python RAM.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api, microsoft_graph_sharepoint` | Pull rate cards, loaded cost bands, and staffing workstream templates from Drive/SharePoint. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Slides` | Read Pricing Pyramid Sheets (`UNFORMATTED_VALUE`) in Proposal Factory Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load proposal staffing JSON workstreams in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and [deal-desk-approval-baseline.md](references/baselines/deal-desk-approval-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [staffing_pyramid_calculator.py](scripts/staffing_pyramid_calculator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.staffing_pyramid_calculator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/staffing_pyramid_calculator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), [workday-hris-traps.md](references/traps/workday-hris-traps.md).
- Surface `CRITICAL_BELOW_20_BLOCKED` whenever blended margin `< 20%` and flag offshore leverage below `55%`.
- Approving proposal pricing concessions or sending commercial staffing schedules requires Practice Lead sign-off (HITL).
