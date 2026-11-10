---
name: citizen-case-eligibility-triager
description: "Evaluates citizen benefits eligibility against household FPL multipliers, enforces mandatory missing-document cure notices rather than automated denials, and flags raw SSN PII Use when triaging citizen benefit, housing aid, or financial assistance case packets. Don't use for evaluating vendor procurement RFP bids (use procurement-tender-evaluator)."
created_by: gemini-agent-plugins
---

# Citizen Benefits Eligibility & Cure Triager

Accelerate public casework queues safely by guaranteeing procedural due process on incomplete applicant files and zero PII echo.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `servicenow_table_api, bigquery_sql_api` | Query case management intake tables and verified document checklist statuses. |
| **Mode B — Google Workspace Fallback** | `Google Docs, Google Sheets, Google Drive` | Read Applicant Intake Packets and Case Triage Sheets in Agency Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load applicant case JSON files in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [statutory_eligibility_engine.py](scripts/statutory_eligibility_engine.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.statutory_eligibility_engine import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/statutory_eligibility_engine.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md).
- NEVER emit a denial recommendation when required documents or income figures are absent — always route to `PENDING_VERIFICATION_CURE_NOTICE` with `cure_deadline_days`.
- Issuing statutory award or adverse-action notices requires licensed agency caseworker sign-off (HITL).
