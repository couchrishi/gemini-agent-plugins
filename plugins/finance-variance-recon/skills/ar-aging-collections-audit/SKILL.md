---
name: ar-aging-collections-audit
description: "Classifies open accounts receivable across Current, 1-30, 31-60, 61-90, and 90+ day buckets while strictly isolating negative credit memos so credits never mask delinquent exposure, computes DSO, and ranks collections priority. Use when auditing AR aging or preparing dunning actions. Don't use for AP vendor invoice matching (use ap-three-way-match)."
created_by: gemini-agent-plugins
---

# AR Aging & Collections Audit

Audit customer receivables accurately across standard aging buckets without allowing unapplied credit memos to disguise `90+` day delinquencies.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api`, `bigquery_sql_api` | Pull open AR subledger items, customer credit memos, and 90-day credit sales denominators. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Gmail`, `Google Drive` | Read AR Aging export Sheets (`UNFORMATTED_VALUE`) and open dispute threads in Finance Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load uploaded AR open-item extracts directly in Python RAM using `view_file`. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [aging_bucket_auditor.py](scripts/aging_bucket_auditor.py) inside persistent `pyrepl` and optionally render priority dunning cards via `emit_a2ui`:

```python
from scripts.aging_bucket_auditor import analyze, render_markdown

res = analyze("ar_open_items.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/aging_bucket_auditor.py --input ar_open_items.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Isolate all negative rows and `CREDIT_MEMO` / `UNAPPLIED_CASH` items into `unapplied_credits_usd` — never net them against `90+` day balances.
- Sending external customer dunning notices or applying credit write-offs requires explicit user confirmation (HITL).
