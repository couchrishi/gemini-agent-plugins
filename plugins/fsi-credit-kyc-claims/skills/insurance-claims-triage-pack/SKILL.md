---
name: insurance-claims-triage-pack
description: "Evaluates insurance claims against policy effective windows, peril exclusions, deductibles, coinsurance retention, peril sublimits, and $100k high-value reserve escalation caps Use when triaging first-notice-of-loss packets or calculating claims reserve payouts. Don't use for underwriting commercial debt covenants (use commercial-credit-memo-analyst)."
created_by: gemini-agent-plugins
---

# Insurance Claims Coverage & Reserve Triage

Apply exact policy terms, exclusions, sublimits, and reserve authority thresholds consistently across property, casualty, and cyber claims.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api` | Query policy schedule tables, sublimits, and FNOL claim records from BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read Policy Schedule Sheets and Claims Intake Docs in Underwriting/Claims Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse claims and policy terms JSON directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [fsi-credit-kyc-baseline.md](references/baselines/fsi-credit-kyc-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [coverage_limit_evaluator.py](scripts/coverage_limit_evaluator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.coverage_limit_evaluator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/coverage_limit_evaluator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Verify `effective_date <= loss_date <= expiration_date` and peril exclusions BEFORE calculating deductible/sublimit math.
- Issuing formal coverage denials or releasing settlement payouts requires explicit Claims Adjuster approval (HITL).
