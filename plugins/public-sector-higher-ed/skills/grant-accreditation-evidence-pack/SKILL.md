---
name: grant-accreditation-evidence-pack
description: "Audits university and public research grant budgets against F&A indirect rate caps, unallowable cost categories, cost-share match ratios, 100% PI effort caps, and accreditation evidence freshness Use when validating sponsored research grant proposals or preparing institutional accreditation evidence binders. Don't use for triaging citizen social benefits cases (use citizen-case-eligibility-triager)."
created_by: gemini-agent-plugins
---

# Grant Budget Allowability & Accreditation Pack

Eliminate sponsor budget rejections and audit findings by catching F&A overages, unallowable charges, and stale evidence before submission.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api` | Pull grant ledger line items, investigator effort tables, and compliance repository timestamps from BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Drive, Google Sheets, Google Docs` | Read Grant Budget Sheets (`UNFORMATTED_VALUE`) and Accreditation Evidence Folders in University Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load grant proposal and accreditation packet JSONs in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [grant_accreditation_validator.py](scripts/grant_accreditation_validator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.grant_accreditation_validator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/grant_accreditation_validator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md).
- Exclude `mtdc_exempt` items (e.g., capital equipment, tuition) and unallowable costs from the Modified Total Direct Cost base before applying `max_indirect_fa_rate_pct`.
- Submitting grant budgets or accreditation self-study packets to external sponsors/accreditors requires Sponsored Programs Officer approval (HITL).
