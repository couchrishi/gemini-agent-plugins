---
name: legacy-code-to-prd
description: "Parses legacy codebase inventories for entrypoints, SQL read/write table couplings, cyclomatic complexity hotspots, and requirement-to-test traceability coverage. Use when scoping monolith modernization or generating functional PRDs. Don't use for reviewing live PR security diffs (use security-pr-readiness-gate)."
created_by: gemini-agent-plugins
---

# Legacy Code to PRD & Traceability Matrix

Reverse-engineer legacy monolith modules into verified entrypoints, database read/write dependency graphs, complexity hotspots, and requirement-to-test traceability matrices before migrating services.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `github_rest_api`, `gitlab_api` | Pull repository source manifests, requirement specs, and CI test mappings via read-only API scopes. |
| **Mode B — Google Workspace Fallback** | `Google Drive`, `Google Docs`, `Google Sheets` | Read exported Architecture Inventory Sheets and Legacy Spec Docs in Engineering Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv`, `.md`, `.txt` | Load uploaded code inventory and requirement JSON/CSV extracts via `view_file` into Python RAM. |

## Org Configuration & Starter Baseline Rule

1. Read [config.json](references/config.json) using `view_file`.
2. Whenever `org_configured` is `false`, apply [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [spec_traceability_matrix.py](scripts/spec_traceability_matrix.py) in `pyrepl` and optionally visualize complexity hotspots with `emit_a2ui`:

```python
from scripts.spec_traceability_matrix import analyze, render_markdown

res = analyze("legacy_inventory.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/spec_traceability_matrix.py --input legacy_inventory.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Flag truncated module scans instead of declaring zero DB couplings, and treat untested critical requirements as modernization blockers.
- Writing private PRD drafts is auto-allowed; creating Jira epics/tickets in bulk or merging repository changes requires explicit user confirmation (HITL).
