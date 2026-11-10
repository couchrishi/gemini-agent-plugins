---
name: kyc-aml-screening-dossier
description: "Resolves cumulative indirect Ultimate Beneficial Ownership percentages across corporate holding layers, lowers EDD threshold to 10% for PEP/high-risk jurisdictions, and flags transaction velocity or structuring alerts Use when conducting KYB corporate onboarding or AML transaction monitoring dossiers. Don't use for computing insurance claim deductibles (use insurance-claims-triage-pack)."
created_by: gemini-agent-plugins
---

# KYB/UBO Ownership & AML Velocity Screener

Uncover indirect nested shell ownership above statutory UBO thresholds and detect structured deposit evasion deterministically.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `fin_kyc_registry_api, bigquery_sql_api` | Pull corporate ownership edges, PEP screens, and 30d/90d cash/wire histories from KYC APIs and BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read Ownership Chart Sheets and AML Case Logs in Financial Crimes Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load corporate graph and transaction log JSONs in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [fsi-credit-kyc-baseline.md](references/baselines/fsi-credit-kyc-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [ubo_velocity_screener.py](scripts/ubo_velocity_screener.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.ubo_velocity_screener import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/ubo_velocity_screener.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Drop UBO threshold from `25%` to `10%` automatically whenever any layer hits a PEP or high-risk jurisdiction, and break ownership cycles safely.
- Filing Suspicious Activity Reports (SAR) or freezing accounts requires explicit MLRO Compliance Officer approval (HITL).
