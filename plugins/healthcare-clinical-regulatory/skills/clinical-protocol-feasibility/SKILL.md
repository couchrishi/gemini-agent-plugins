---
name: clinical-protocol-feasibility
description: "Cross-checks clinical trial Schedule of Assessments visit windows against primary/secondary endpoints and calculates screen-fail-adjusted enrollment capacity across IRB sites Use when reviewing Phase II/III clinical trial protocol synopses or site feasibility plans. Don't use for scoring adverse event ICSR intake timeliness (use pharmacovigilance-safety-intake)."
created_by: gemini-agent-plugins
---

# Clinical Protocol SoA & Enrollment Feasibility

Prevent costly protocol amendments and stalled accrual by catching SoA-to-endpoint mismatches and screen-fail gaps upfront.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `ctms_fhir_api, bigquery_sql_api` | Pull visit schedules, endpoints, and site enrollment/IRB metrics from CTMS and BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read SoA Matrix Sheets (`UNFORMATTED_VALUE`) and Site Feasibility Docs in Clinical Ops Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load clinical protocol JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [soa_endpoint_validator.py](scripts/soa_endpoint_validator.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.soa_endpoint_validator import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/soa_endpoint_validator.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Exclude non-IRB-approved sites from active accrual projections and discount gross screened patients by `1 - screen_fail_rate_pct/100`.
- Approving clinical protocol amendments or site activations requires Clinical Development Lead confirmation (HITL).
