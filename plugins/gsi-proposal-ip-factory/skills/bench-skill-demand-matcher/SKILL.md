---
name: bench-skill-demand-matcher
description: "Matches open project role requirements against available bench talent using deterministic skill overlap %, start-date delay limits, and hourly gross margin ranking Use when staffing sold engagements from bench/roll-off pools or flagging subcontract gaps. Don't use for scoring candidate interview debriefs (use structured-hiring-rubric)."
created_by: gemini-agent-plugins
---

# Bench Skill & Project Demand Matcher

Fill consulting roles faster from internal bench capacity while catching critical skill gaps that need subcontracting early.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `workday_raas_api, google_drive_api` | Pull bench roll-off rosters from Workday and project demand seats from PSA/Drive. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Weekly Bench Roster Sheets (`UNFORMATTED_VALUE`) and Demand Trackers in Resource Management Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load demands and bench consultant JSON payloads in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and [deal-desk-approval-baseline.md](references/baselines/deal-desk-approval-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [talent_bench_matcher.py](scripts/talent_bench_matcher.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.talent_bench_matcher import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/talent_bench_matcher.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), [workday-hris-traps.md](references/traps/workday-hris-traps.md).
- Never force-match candidates below `min_skill_overlap_pct` or delayed past `max_start_delay_days`; label gaps `EXTERNAL_SUBCONTRACT_REQUIRED`.
- Confirming consultant project assignments requires Resource Manager and Consultant Lead confirmation (HITL).
