---
name: security-pr-readiness-gate
description: "Scans unified pull/merge request diffs and dependency manifests for hardcoded credentials, removed authz decorators, destructive or locking DB migrations, and breaking API route removals. Use when gating PRs before review or merge. Don't use for reverse-engineering monoliths (use legacy-code-to-prd)."
created_by: gemini-agent-plugins
---

# Security & Migration PR Readiness Gate

Inspect unified GitHub/GitLab diffs and dependency manifests deterministically in RAM to catch secret leaks, authorization decorator removals, destructive DDL, and breaking API removals prior to merge.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `github_rest_api`, `gitlab_api` | Fetch PR/MR unified diff patches and dependency lockfile diffs via read-only repository tokens. |
| **Mode B — Google Workspace Fallback** | `Google Drive`, `Google Docs`, `Google Sheets` | Read exported PR Diff attachments or Security Review Docs in Engineering Shared Drives. |
| **Mode C — Direct File Upload** | `.diff`, `.json`, `.txt` | Load uploaded `.diff`/`.patch` or structured PR JSON payloads via `view_file` in Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) using `view_file`.
2. Whenever `org_configured` is `false`, apply [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [diff_risk_inspector.py](scripts/diff_risk_inspector.py) in `pyrepl` and render findings via `emit_a2ui`:

```python
from scripts.diff_risk_inspector import analyze, render_markdown

res = analyze("pr_diff.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/diff_risk_inspector.py --input pr_diff.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Enforce [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Never echo full raw secret strings in chat outputs; report file/line coordinates and finding categories only.
- Merging PRs, approving reviews, or applying DB migrations always requires explicit user confirmation (HITL).
