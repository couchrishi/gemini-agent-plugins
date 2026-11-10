---
name: sow-scope-margin-auditor
description: "Audits Statement of Work deliverables and commercial clauses for unbounded scope creep language, missing objective acceptance criteria, extended milestone acceptance windows, and margin breaches Use when reviewing draft client SOWs before bid approval or signature. Don't use for matching available consultants to open project roles (use bench-skill-demand-matcher)."
created_by: gemini-agent-plugins
---

# SOW Scope Creep & Margin Auditor

Eliminate fixed-fee scope creep traps and missing deliverable acceptance criteria before signing consulting SOWs.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api, microsoft_graph_sharepoint` | Read draft SOW agreements and deliverable registers from SharePoint or Drive. |
| **Mode B — Google Workspace Fallback** | `Google Docs, Google Sheets, Google Drive` | Inspect SOW Docs (`includeTabsContent`) and Bid Review Sheets in Delivery Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load SOW clause and deliverable JSON extracts in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and [deal-desk-approval-baseline.md](references/baselines/deal-desk-approval-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [sow_margin_linter.py](scripts/sow_margin_linter.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.sow_margin_linter import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/sow_margin_linter.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), [workday-hris-traps.md](references/traps/workday-hris-traps.md).
- Phrases like `all work required`, `unlimited revisions`, or margin `< 20%` MUST produce `BLOCKED_SCORE_9`.
- Waiving missing acceptance criteria or routing risky SOWs for client transmission requires Practice VP approval (HITL).
