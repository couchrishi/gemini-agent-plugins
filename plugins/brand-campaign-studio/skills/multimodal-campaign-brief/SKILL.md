---
name: multimodal-campaign-brief
description: "Builds audience-by-channel and funnel deliverable matrices, flags coverage gaps, checks budget caps, and identifies late critical-path assets Use when planning integrated campaigns or reviewing pre-launch deliverable readiness. Don't use for linting individual ad headlines for banned words (use brand-voice-compliance-gate)."
created_by: gemini-agent-plugins
---

# Multimodal Campaign Brief & Asset Matrix

Guarantee full funnel coverage, budget discipline, and adequate production lead time across integrated marketing launches.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api, microsoft_graph_sharepoint` | Read campaign briefs, media plans, and production schedules from Drive/SharePoint. |
| **Mode B — Google Workspace Fallback** | `Google Docs, Google Sheets, Google Slides` | Inspect Launch Plan Sheets (`UNFORMATTED_VALUE`) and Creative Brief Docs in Marketing Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load campaign deliverable matrix JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [campaign_asset_matrix.py](scripts/campaign_asset_matrix.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.campaign_asset_matrix import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/campaign_asset_matrix.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Missing audience×channel cells or missing Awareness/Consideration/Conversion stages MUST appear in `missing_channel_cells`/`missing_funnel_cells` (absent != covered).
- Approving media budget reallocations or overriding launch readiness blocks requires Marketing Lead confirmation (HITL).
