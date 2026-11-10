---
name: cross-source-knowledge-synthesis
description: "Synthesizes cross-source answers across Drive, SharePoint, and Confluence, ranking authority and detecting conflicting numerical/date claims with 100% citation verification. Use when reconciling conflicting internal docs or writing cited executive briefs. Don't use for single-policy jurisdiction lookups (use policy-sop-answering) or corpus metadata cleanup (use knowledge-gap-freshness-audit)."
created_by: gemini-agent-plugins
---

# Cross-Source Knowledge Synthesis

Synthesize multi-repository evidence across Google Workspace, SharePoint, and Confluence while resolving authority conflicts, flagging truncated search scopes, and verifying 100% citation coverage.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api`, `microsoft_graph_sharepoint`, `atlassian_confluence_cloud` | Search across Shared Drives (`includeItemsFromAllDrives=true`), SharePoint sites (trailing `/` on KQL `path:`), and Confluence spaces. Capture `total_available` and any `403`/blocked sources. |
| **Mode B — Google Workspace Fallback** | `Google Drive`, `Google Docs`, `Google Sheets` | Read all document tabs (`includeTabsContent`) and Shared Drive excerpts via Workspace search when 3P connectors are unavailable. |
| **Mode C — Direct File Upload** | `.json`, `.csv`, `.md`, `.txt` | Load uploaded search exports or passage lists directly via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) using `view_file` (or check a user-supplied tenant config file).
2. Read `org_configured`. Whenever `org_configured` is `false`, apply the bundled starter rubrics in [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md), and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [citation_conflict_auditor.py](scripts/citation_conflict_auditor.py) in Python RAM so raw excerpts and scoring math never consume prompt tokens:

```python
import json
from scripts.citation_conflict_auditor import analyze, render_markdown

with open("references/config.json") as f:
    cfg = json.load(f)

result = analyze("search_hits.json", config=cfg)
print(render_markdown(result))
```

CLI fallback outside persistent `pyrepl`:

```bash
python3 scripts/citation_conflict_auditor.py --input search_hits.json --config references/config.json --format markdown
```

Emit interactive source comparison scorecards via `emit_a2ui` when presenting multi-repo conflict tables.

## Enterprise Traps & HITL Confirmation Gate

- Read and apply [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Treat `TRUNCATION_WARNING` and `UNVERIFIED_INSUFFICIENT_SCOPE` as abstention or caveat triggers rather than declaring "no conflicts".
- Creating private Google Docs drafts is auto-allowed; publishing Confluence pages or broadcasting email digests requires explicit user confirmation (HITL).
