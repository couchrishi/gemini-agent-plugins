# Logistics Zone SLA & Fault Attribution (`logistics-sla-dispute-resolver`)

Evaluates SuperApp delivery SLA disputes by isolating merchant prep delays from courier transit delays, honoring weather force-majeure carveouts, and calculating refund split liability. Deterministic computation executes via [`scripts/zone_sla_dispute_analyzer.py`](scripts/zone_sla_dispute_analyzer.py). Domain guards enforced: Proportional fault allocation when both prep and transit overran SLA; Places missing delivery timestamps in MISSING_TELEMETRY_HOLD. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Delivery Operations / Dispute Resolution Lead**: Triggered when adjudicating late on-demand delivery claims between merchant prep delays and courier transit; applies severe-weather waivers, `5`-minute SLA grace tolerances, and proportional fault attribution before calculating wallet refunds.
- **SuperApp Rider & Merchant Ops Analyst**: Triggered when preventing blanket carrier penalties or customer over-refunds (`>$50` HITL ceiling); routes high-value goodwill refunds through explicit Trust/Ops authorization.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`logistics-sla-dispute-resolver.zip`](../../../../dist/skills/logistics-sla-dispute-resolver.zip) (or the full department bundle [`marketplace-superapp-ops.zip`](../../../../dist/bundles/marketplace-superapp-ops.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Postgres`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`PSP Settlement Ledger & Marketplace Catalog MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx`](../../../../examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/logistics-sla-dispute-resolver` or `@logistics-sla-dispute-resolver`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.zone_sla_dispute_analyzer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"disputes": [{"order_id": r.get("Custom order_id"), "promised_total_minutes": r.get("Custom promised_total_minutes"), "actual_total_minutes": r.get("Custom actual_total_minutes")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/marketplace-superapp-ops/skills/logistics-sla-dispute-resolver/scripts/zone_sla_dispute_analyzer.py \
  --input examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx \
  --config plugins/marketplace-superapp-ops/skills/logistics-sla-dispute-resolver/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `zone_sla_dispute_analyzer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Postgres`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`PSP Settlement Ledger & Marketplace Catalog MCP server`) via `remote_cli mcp`):** "Adjudicate Veloce SuperApp order 42 minutes late where merchant kitchen took 45m (15m SLA) and courier took 20m."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate Drive SLA Dispute Sheet with verified storm alert and missing GPS dropoff timestamp."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx`](../../../../examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx) and ask: "Adjudicate the late delivery SLA disputes in `Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx` by splitting proportional fault between merchant kitchen prep delays and courier transit delays, honoring weather waivers and flagging missing GPS dropoff telemetry."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `2` logistics disputes (`0` weather-waived) in `Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx` established **`1` verified SLA breach on `ORD-MK-8821` (`Z-DOWNTOWN`, `35` mins late, `$95.00` refund attributed `$89.57` merchant / `$5.43` platform)** and placed **`ORD-MK-8822` on `MISSING_TELEMETRY_HOLD`** (`$0.00` automated refund).

- **Proportional Fault Math (`ORD-MK-8821`):** Split `$95.00` refund liability accurately between merchant prep excess (`$89.57`, `94.3%`) and courier transit (`$5.43`, `5.7%`).
- **Missing Telemetry Protection:** Refused automatic refund or carrier penalty on `ORD-MK-8822` (`Z-HARBOR`) where dropoff timestamp telemetry was missing (`HOLD_HITL`).
- **Approval Confirmation Prompt:** Confirm Trust/Ops approval before applying `$89.57` merchant recovery or releasing adjusted merchant payouts via your connected payout / PSP MCP server (gated by `Auto-Guardian`) (`$95.00` refund exceeds standard `$50` auto-cap).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx`](../../../../examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx) (`130.6 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Logistics Zone SLA Dispute Resolution Matrix

- **Evaluated:** 2 | **Valid Breaches:** 1 | **Weather Waived:** 0 | **Total Refund Liability:** $95.00

| Order | Zone | Late Mins | Attribution | Refund $ | Merchant Share | Platform Share | HITL Gate |
| :--- | :--- | ---: | :--- | ---: | ---: | ---: | :--- |
| `ORD-MK-8821` | Z-DOWNTOWN | 35 | `SHARED_MERCHANT_COURIER_BREACH` | $95.00 | $89.57 | $5.43 | HOLD_HITL |
| `ORD-MK-8822` | Z-HARBOR | 0 | `MISSING_TELEMETRY_HOLD` | $0.00 | $0.00 | $0.00 | HOLD_HITL |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Payout Settlement Reconciliation` routine via `schedule_task`:

```text
Schedule recurring job "Daily Payout Settlement Reconciliation" on cron `15 4 * * *` (`UTC`) with instruction: "Run daily merchant payout vs PSP bank settlement reconciliation via scripts/payout_ledger_reconciler.py and escalate negative clawback balances before bank cutoff."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `disputes`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `disputes` requires [`order_id`; `promised_total_minutes`; `actual_total_minutes`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `sla_grace_minutes` | `integer` | `5` | On-demand delivery promise grace window in minutes. |
| `high_value_payout_hitl_usd` | `number` | `50.0` | Customer SLA refund threshold requiring Trust/Ops HITL sign-off. |

See [`../../README.md`](../../README.md) for the `marketplace-superapp-ops` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
