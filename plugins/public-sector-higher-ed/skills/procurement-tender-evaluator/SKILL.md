---
name: procurement-tender-evaluator
description: "Screens sealed public procurement bids for debarment, conflict-of-interest, tax clearance, and minimum technical score BEFORE normalizing commercial price scores and ranking finalists Use when evaluating competitive government or university RFP vendor tender submissions. Don't use for auditing internal research grant budgets (use grant-accreditation-evidence-pack)."
created_by: gemini-agent-plugins
---

# Public Procurement Tender Weighted Evaluator

Prevent invalidated public tender awards by disqualifying non-compliant or debarred bidders before price normalization.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_table_api, bigquery_sql_api` | Pull sealed bid compliance checklists, evaluator technical scores, and commercial bid totals. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read Sealed Bid Tabulation Sheets (`UNFORMATTED_VALUE`) and Compliance Attestations in Procurement Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse tender bid JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [tender_weighted_scorer.py](scripts/tender_weighted_scorer.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.tender_weighted_scorer import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/tender_weighted_scorer.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md).
- Compute `lowest_compliant_price_usd` ONLY from compliant bidders — never let an artificially cheap debarred bid distort commercial score normalization.
- Issuing public notice of intent to award requires Evaluation Board Chair sign-off (HITL).
