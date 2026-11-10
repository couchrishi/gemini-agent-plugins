---
name: troubleshooting-tree-author
description: "Audits interactive troubleshooting flowcharts using graph traversal to detect cycles, unreachable orphan nodes, broken branch targets, dead-end questions, and excessive hop depth Use when authoring or QA-validating support agent diagnostic flows before publishing. Don't use for mining CSAT survey verbatims (use csat-churn-signal-miner)."
created_by: gemini-agent-plugins
---

# Troubleshooting Decision Tree Author & Validator

Verify structural graph soundness of interactive support playbooks before deploying broken loops to frontline agents.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_csm_api` | Pull CSM guided decision flows and diagnostic scripts. |
| **Mode B — Google Workspace Fallback** | `Google Docs, Google Drive` | Read Support Playbook Docs in Customer Ops Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load decision tree graph JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [decision_tree_validator.py](scripts/decision_tree_validator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.decision_tree_validator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/decision_tree_validator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [salesforce-crm-soql-traps.md](references/traps/salesforce-crm-soql-traps.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Any graph with `cycles_detected`, `dead_end_nodes`, `unreachable_nodes`, or `broken_references` MUST mark `graph_valid: false`.
- Deploying validated troubleshooting trees into live agent consoles requires Knowledge Lead approval (HITL).
