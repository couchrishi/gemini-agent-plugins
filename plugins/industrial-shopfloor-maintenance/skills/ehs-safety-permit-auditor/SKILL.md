---
name: ehs-safety-permit-auditor
description: "Audits high-hazard Permit-to-Work packages against Lockout/Tagout isolation, atmospheric O2/LEL safety tolerances, gas-test recency, fire watch, and worker certifications Use when verifying confined-space, hot-work, or high-voltage electrical permits before shopfloor entry. Don't use for calculating MRO spare-part inventories (use asset-reliability-spares-planner)."
created_by: gemini-agent-plugins
---

# EHS Permit-to-Work & LOTO Safety Auditor

Block unsafe industrial maintenance permits automatically whenever LOTO, gas readings, or safety certifications are missing or out of bounds.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `sap_odata_api` | Read SAP EHS work-clearance management permits and isolation certificates. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read Daily EHS Permit Checklist Sheets in Plant Safety Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse Permit-to-Work JSON packages in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [hse_permit_checker.py](scripts/hse_permit_checker.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.hse_permit_checker import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/hse_permit_checker.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md).
- Life-safety rule: missing O2/LEL readings or `loto_isolated != true` on confined-space/high-voltage work MUST return `STOP_WORK_BLOCKED` (never treat absent as safe!).
- Final Permit-to-Work authorization always requires live physical sign-off by a qualified Area Safety Authority (HITL).
