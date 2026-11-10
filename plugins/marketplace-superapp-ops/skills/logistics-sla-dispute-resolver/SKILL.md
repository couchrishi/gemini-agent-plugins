---
name: logistics-sla-dispute-resolver
description: "Evaluates SuperApp delivery SLA disputes by isolating merchant prep delays from courier transit delays, honoring weather force-majeure carveouts, and calculating refund split liability Use when adjudicating courier/merchant late-delivery disputes or batch SLA refund payouts. Don't use for moderating prohibited catalog items (use merchant-catalog-trust-gate)."
created_by: gemini-agent-plugins
---

# Logistics Zone SLA & Fault Attribution

Eliminate arbitrary 50/50 split penalties by measuring prep overrun vs zone transit overrun deterministically.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `bigquery_sql_api, rest_webhook_api` | Pull order promised ETA, kitchen/merchant ready scan, and courier GPS dropoff logs from BigQuery. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Drive` | Read Zone Delivery SLA Dispute Sheets (`UNFORMATTED_VALUE`) in Logistics Ops Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse order SLA dispute JSONs directly in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [itsm-sla-severity-baseline.md](references/baselines/itsm-sla-severity-baseline.md) and [finance-materiality-baseline.md](references/baselines/finance-materiality-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [zone_sla_dispute_analyzer.py](scripts/zone_sla_dispute_analyzer.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.zone_sla_dispute_analyzer import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/zone_sla_dispute_analyzer.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), [bigquery-sap-erp-traps.md](references/traps/bigquery-sap-erp-traps.md).
- Place orders with null `actual_total_minutes` in `MISSING_TELEMETRY_HOLD` rather than zero-delay false negatives (`absent-is-not-zero.md`).
- Disbursing refunds >= $50 or reversing merchant fault deductions requires Logistics Ops Lead confirmation (HITL).
