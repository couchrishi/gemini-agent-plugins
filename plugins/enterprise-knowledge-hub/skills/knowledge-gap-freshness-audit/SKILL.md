---
name: knowledge-gap-freshness-audit
description: "Audits enterprise Drive, SharePoint, and Confluence inventories for overdue review dates, null timestamps, departed owners, near-duplicate titles, and unindexed ticket gaps. Use when running periodic KB hygiene or identifying missing self-service SOPs. Don't use for answering employee policy questions (use policy-sop-answering)."
created_by: gemini-agent-plugins
---

# Knowledge Gap & Freshness Audit

Continuously measure enterprise corpus health across Google Drive, SharePoint, and Confluence while pairing missing/stale documentation against top support ticket volume.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api`, `microsoft_graph_sharepoint`, `atlassian_confluence_cloud`, `servicenow_table_api` | Paginate full metadata (`nextPageToken`, `@odata.nextLink`, `X-Total-Count`) across document libraries and resolved ticket topic clusters. |
| **Mode B — Google Workspace Fallback** | `Google Drive`, `Google Sheets` | Read corpus inventory export Sheets and support ticket summary Sheets from Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load uploaded document inventory and ticket-topic CSV/JSON datasets directly in RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Apply `stale_review_days` and `duplicate_title_similarity_threshold`. Whenever `org_configured` is `false`, apply [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp the deliverable header verbatim:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [corpus_hygiene_scanner.py](scripts/corpus_hygiene_scanner.py) in `pyrepl` (or schedule weekly runs via `schedule_task` and render dashboards via `emit_a2ui`):

```python
from scripts.corpus_hygiene_scanner import analyze, render_markdown

res = analyze("corpus_inventory.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/corpus_hygiene_scanner.py --input corpus_inventory.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Treat null `last_reviewed_at` timestamps as `unverified_null_reviews`, never "fresh".
- Never archive, delete, or revoke permissions on stale files without explicit user confirmation (HITL).
