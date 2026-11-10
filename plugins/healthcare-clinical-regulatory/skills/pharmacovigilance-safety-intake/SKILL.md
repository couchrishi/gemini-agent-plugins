---
name: pharmacovigilance-safety-intake
description: "Validates Adverse Event intake reports against the 4 mandatory ICH ICSR criteria, computes exact 7-day fatal and 15-day expedited statutory due dates, and detects raw SSN/email/phone PHI Use when triaging pharmacovigilance adverse event reports or checking regulatory E2B reporting deadlines. Don't use for matching payer prior authorization criteria (use prior-auth-medical-necessity)."
created_by: gemini-agent-plugins
---

# Pharmacovigilance E2B ICSR Completeness & SLA

Enforce strict 4-criteria ICH validity, zero-day-slip regulatory clocks, and automated PHI scrubbing gates on safety intake.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `ctms_fhir_api, bigquery_sql_api` | Pull de-identified safety intake cases and awareness timestamps from PV safety databases. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read PV Case Intake Logs (`UNFORMATTED_VALUE`) in Drug Safety Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load safety intake JSON extracts in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [icsr_completeness_checker.py](scripts/icsr_completeness_checker.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.icsr_completeness_checker import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/icsr_completeness_checker.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Never transmit raw narratives containing SSN/email/phone patterns; immediately flag `PHI_REDACTION_REQUIRED`.
- Regulatory E2B(R3) transmission to FDA/EMA requires Qualified Person for Pharmacovigilance (QPPV) approval (HITL).
