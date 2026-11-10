---
name: prior-auth-medical-necessity
description: "Evaluates healthcare prior authorization clinical packets deterministically against payer CPT medical policies, ICD-10 diagnosis prefixes, prior step-therapy trials, and required diagnostic labs Use when compiling medical necessity checklists for clinician or payer medical director review. Don't use for auditing clinical trial Schedules of Assessments (use clinical-protocol-feasibility)."
created_by: gemini-agent-plugins
---

# Prior Authorization Medical Necessity Reviewer

Accelerate clinical review accuracy with deterministic policy criterion-by-criterion matching while keeping all determinations clinician-owned.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `ctms_fhir_api` | Pull de-identified patient clinical summaries, ICD-10 codes, medication step history, and labs via FHIR. |
| **Mode B — Google Workspace Fallback** | `Google Docs, Google Sheets, Google Drive` | Read Payer Policy Matrix Docs and Prior-Auth Checklist Sheets in Utilization Management Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load de-identified prior auth request & policy JSONs in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [medical_criteria_matcher.py](scripts/medical_criteria_matcher.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.medical_criteria_matcher import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/medical_criteria_matcher.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Never issue an autonomous medical denial; flag unmet criteria for `PEER_REVIEW_MISSING_DOCS` or `MEDICAL_DIRECTOR_REVIEW`.
- Final prior authorization approvals and clinical medical-necessity denials strictly require licensed Physician / Medical Director sign-off (HITL).
