---
name: brand-voice-compliance-gate
description: "Lints ad and campaign copy against prohibited claims, mandatory legal disclaimers, sentence readability, and channel character budgets Use when reviewing outbound campaign copy, search ads, or landing page drafts before launch. Don't use for auditing multi-locale glossary translations (use market-localization-adapter)."
created_by: gemini-agent-plugins
---

# Brand Voice & Claims Compliance Gate

Catch unsubstantiated superlatives, missing regulatory disclaimers, and truncated ad headlines before creative reaches paid channels.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api, microsoft_graph_sharepoint` | Pull brand guidelines and draft creative files from Drive/SharePoint. |
| **Mode B — Google Workspace Fallback** | `Google Docs, Google Slides, Google Drive` | Inspect Campaign Copy Docs and Brand Playbooks in Marketing Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse uploaded campaign copy JSON drafts directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [copy_compliance_linter.py](scripts/copy_compliance_linter.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.copy_compliance_linter import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/copy_compliance_linter.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Any asset with banned guarantees or un-disclaimed `% savings` / `ROI` / `APR` claims MUST return `BLOCKED_COMPLIANCE_VIOLATION`.
- Publishing assets to live paid media or CMS endpoints requires explicit Brand/Legal sign-off (HITL).
