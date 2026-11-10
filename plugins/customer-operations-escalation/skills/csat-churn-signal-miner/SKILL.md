---
name: csat-churn-signal-miner
description: "Quantifies CSAT/NPS survey driver themes weighted by detractor ARR while keeping unrated null responses out of rating denominators and alerting on churn-intent verbatims Use when analyzing quarterly CSAT/NPS verbatims or prioritizing product/support churn drivers. Don't use for scoring single live Sev1 outages (use critical-escalation-warroom)."
created_by: gemini-agent-plugins
---

# CSAT & NPS Verbatim Churn Signal Miner

Turn unstructured CSAT/NPS survey noise into an ARR-weighted root-cause pareto with strict denominator hygiene.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `salesforce_soql_api, servicenow_csm_api` | Pull survey responses joined cleanly to Account ARR in Salesforce/CSM. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Quarterly CSAT/NPS Survey Export Sheets (`UNFORMATTED_VALUE`) in Customer Ops Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load survey verbatim JSON extracts in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [verbatim_driver_quantifier.py](scripts/verbatim_driver_quantifier.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.verbatim_driver_quantifier import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/verbatim_driver_quantifier.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [salesforce-crm-soql-traps.md](references/traps/salesforce-crm-soql-traps.md), [servicenow-jira-itsm-traps.md](references/traps/servicenow-jira-itsm-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Unrated rows (`csat_score is None`) MUST be excluded from `avg_csat` denominator and tracked in `unrated_csat_excluded` — never treat null as 0!
- Triggering automated CSM retention outreach campaigns requires Customer Success Manager confirmation (HITL).
