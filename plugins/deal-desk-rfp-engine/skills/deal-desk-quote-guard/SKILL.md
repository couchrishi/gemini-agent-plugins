---
name: deal-desk-quote-guard
description: "Validates multi-year SaaS quotes and ramp schedules for net effective discount, Year-1 vs blended ACV, TCV, gross margin floors, and non-standard terms. Use when reviewing customer quotes for Deal Desk approval. Don't use for CRM pipeline hygiene audits (use pipeline-hygiene-slippage)."
created_by: gemini-agent-plugins
---

# Deal Desk Quote Guard

Calculate deterministic multi-year ramp ACV, TCV, net effective discounts, and blended gross margins against Deal Desk tier floors before submitting pricing exceptions.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `salesforce_soql_api`, `google_drive_api` | Pull Quote, QuoteLineItem, COGS rate card, and payment term overrides from Salesforce CPQ / Drive. |
| **Mode B — Google Workspace Fallback** | `Google Sheets`, `Google Docs`, `Google Drive` | Read Pricing Calculator Sheets (`UNFORMATTED_VALUE`) and Quote Summary Docs in Revenue Ops Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Parse uploaded quote JSON payloads directly in Python RAM using `view_file`. |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, apply [deal-desk-approval-baseline.md](references/baselines/deal-desk-approval-baseline.md) and [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md), and stamp the deliverable header verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [deal_margin_validator.py](scripts/deal_margin_validator.py) in `pyrepl` and optionally render approval cards with `emit_a2ui`:

```python
from scripts.deal_margin_validator import analyze, render_markdown

res = analyze("quote.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/deal_margin_validator.py --input quote.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [salesforce-crm-soql-traps.md](references/traps/salesforce-crm-soql-traps.md), [chain-denominator-seams.md](references/traps/chain-denominator-seams.md), and [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Always compute Year-1 ACV separately from multi-year blended ACV so back-end ramps cannot disguise margin erosion.
- Approving escalated quotes (`Tier 1`–`Tier 3`) or mutating Salesforce quote records requires explicit user confirmation (HITL).
