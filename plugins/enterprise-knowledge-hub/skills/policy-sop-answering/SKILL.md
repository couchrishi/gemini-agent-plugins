---
name: policy-sop-answering
description: "Answers policy and SOP questions by filtering clauses strictly by jurisdiction, legal entity, effective date, and published status, enforcing abstention on missing coverage. Use when employees ask HR, expense, security, or procurement policy questions. Don't use for synthesizing informal project wikis (use cross-source-knowledge-synthesis) or contract redlining."
created_by: gemini-agent-plugins
---

# Policy & SOP Answering

Deliver authoritative policy and SOP guidance scoped strictly by jurisdiction, legal entity, and effective date, refusing to cite superseded versions, unpublished drafts, or uncovered regions.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `google_drive_api`, `microsoft_graph_sharepoint`, `atlassian_confluence_cloud` | Query published policy repositories; filter out SharePoint minor draft versions (`_ModerationStatus != 0`) and expired pages. |
| **Mode B — Google Workspace Fallback** | `Google Drive`, `Google Docs`, `Google Sheets` | Inspect Policy Index Sheets (`UNFORMATTED_VALUE`) and all nested tabs inside multi-tabbed Google Docs SOP manuals. |
| **Mode C — Direct File Upload** | `.json`, `.csv`, `.md`, `.txt` | Parse uploaded clause libraries or policy tables via `view_file` and execute scope matching in RAM. |

## Org Configuration & Starter Baseline Rule

1. Read [config.json](references/config.json) with `view_file`.
2. Verify `org_configured` and `allow_draft_versions_in_answers`.
3. Whenever `org_configured` is `false`, follow [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp the deliverable header verbatim:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Run [policy_scope_matcher.py](scripts/policy_scope_matcher.py) in `pyrepl` before formulating any policy determination:

```python
from scripts.policy_scope_matcher import analyze, render_markdown

res = analyze(
    "policy_clauses.json",
    config="references/config.json",
    query="What is the bereavement leave entitlement?",
    jurisdiction="SG",
    entity="Cymbal Financial",
    as_of_date="2026-11-10",
)
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/policy_scope_matcher.py --input policy_clauses.json --config references/config.json --jurisdiction SG --entity "Cymbal Financial" --query "bereavement leave" --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Enforce [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Whenever `summary.abstained` is `true` (`ABSTENTION_NO_EFFECTIVE_COVERAGE`), explicitly state the uncovered jurisdiction/entity instead of guessing from another country's policy.
- Answering questions and writing private drafts are read/draft-only; modifying published SOPs or emailing policy rulings to distribution lists requires explicit user confirmation (HITL).
