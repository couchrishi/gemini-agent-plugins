---
name: commercial-credit-memo-analyst
description: "Computes commercial credit covenant ratios (DSCR, Net Leverage, Interest Coverage, Liquidity) across Base Case and multi-factor revenue and interest rate stress shocks Use when underwriting commercial loans or running quarterly portfolio covenant stress tests. Don't use for screening corporate beneficial ownership for AML (use kyc-aml-screening-dossier)."
created_by: gemini-agent-plugins
---

# Commercial Credit Memo & Stress Analyst

Evaluate borrower debt service resilience across base and severe stress scenarios without arithmetic drift.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api` | Pull borrower EBITDA, debt schedule, floating debt share, and liquidity figures from BigQuery spreads. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read Credit Spreading Sheets (`UNFORMATTED_VALUE`) and Borrower Financial Packages in Commercial Banking Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load borrower financial spread JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [fsi-credit-kyc-baseline.md](references/baselines/fsi-credit-kyc-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [credit_covenant_stress.py](scripts/credit_covenant_stress.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.credit_covenant_stress import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/credit_covenant_stress.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Align financial statement periods across EBITDA, Interest, and Debt balances (avoid TTM vs quarterly denominator mismatches).
- Issuing loan approvals, term sheets, or covenant waivers requires explicit Credit Committee sign-off (HITL).
