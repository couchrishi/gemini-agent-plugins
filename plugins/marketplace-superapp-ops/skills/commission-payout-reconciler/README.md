# Commission, FX & Merchant Payout Reconciler (`commission-payout-reconciler`)

Reconciles merchant gross GMV, marketplace commission fees, PSP processing charges, promo co-funding, refunds, FX conversion, and bank settlement wires. Deterministic computation executes via [`scripts/payout_ledger_reconciler.py`](scripts/payout_ledger_reconciler.py). Domain guards enforced: Applies FX conversion cleanly after local fee and promo netting; Flags negative settlement clawbacks ahead of normal reconciled accounts. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Marketplace Financial Settlement Controller**: Triggered when reconciling merchant gross sales, `15%` platform take-rate, clawbacks, and PSP bank wires; catches cross-currency EUR/USD payout mismatches, surfaces negative clawback balances, and flags variances exceeding `$5.00`.
- **Merchant Payout Ops Analyst**: Triggered when validating daily/weekly Stripe or Adyen settlement batches before bank release; holds anomalous net settlements (`EUR` vs `USD` or fee drift) prior to wire execution.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`commission-payout-reconciler.zip`](../../../../dist/skills/commission-payout-reconciler.zip) (or the full department bundle [`marketplace-superapp-ops.zip`](../../../../dist/bundles/marketplace-superapp-ops.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Postgres`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`PSP Settlement Ledger & Marketplace Catalog MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx`](../../../../examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/commission-payout-reconciler` or `@commission-payout-reconciler`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.payout_ledger_reconciler import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"merchant_payouts": [{"merchant_id": r.get("Custom merchant_id"), "gross_gmv_local": r.get("Custom gross_gmv_local"), "actual_psp_settled_amount": r.get("Custom actual_psp_settled_amount")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/marketplace-superapp-ops/skills/commission-payout-reconciler/scripts/payout_ledger_reconciler.py \
  --input examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx \
  --config plugins/marketplace-superapp-ops/skills/commission-payout-reconciler/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `payout_ledger_reconciler.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Postgres`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`PSP Settlement Ledger & Marketplace Catalog MCP server`) via `remote_cli mcp`):** "Reconcile Veloce SuperApp payouts where Merchant A has high refunds causing -$420 balance and Merchant B has $180 FX wire mismatch."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Weekly Merchant Payout Sheet in Drive for commission/promo split discrepancies."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx`](../../../../examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx) and ask: "Reconcile the weekly merchant gross GMV, platform commissions, promo splits, and PSP settlement transfers in `Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx`, catching currency EUR/USD mismatches and negative merchant clawback balances before payout release."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing `3` merchant settlements totaling **`$20,030.20` expected net payout** in `Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx` **flagged exceptions across all `3` merchants (`$1,269.80` aggregate variance)**—including **`1` negative clawback risk (`MRC-SILO-A`, `$-1,480.00`)** and cross-currency/fee drift (`MRC-EURO-B` `$-500.20`, `MRC-OK-01` `$+290.00`).

- **Negative Clawback Hold (`MRC-SILO-A` — Bistro Veloce):** High refund volume drove expected net payout to **`$-1,480.00`** vs. `$0.00` PSP transfer (`+$1,480.00` variance).
- **PSP Settlement Drift (`MRC-EURO-B` & `MRC-OK-01`):** `Atelier Nord` (`$13,300.20` expected vs `$12,800.00` actual, `-$500.20` FX/fee gap) and `Verified Goods` (`$8,210.00` vs `$8,500.00`, `+$290.00` overpayment) both breach the `$5.00` payout tolerance.
- **Approval Confirmation Prompt:** Payout batch release via your connected PSP MCP server is blocked while `exception_count > 0`; reconcile the `3` variances first or hold `MRC-SILO-A` / `MRC-OK-01` before requesting treasury approval.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx`](../../../../examples/marketplace-superapp-ops/Apex_Marketplace_Trust_Disputes_and_Payouts_Sample.xlsx) (`136.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Marketplace Commission & Merchant Payout Reconciliation

- **Merchants:** 3 | **Exceptions:** 3 | **Clawback Risk:** 1 | **Net Variance:** $1,269.80

| Merchant | Gross GMV | Expected Net | Actual PSP | Variance | Status |
| :--- | ---: | ---: | ---: | ---: | :--- |
| `MRC-SILO-A` Bistro Veloce | $20,000.00 | $-1,480.00 | $0.00 | $+1,480.00 | `NEGATIVE_CLAWBACK_RISK` |
| `MRC-EURO-B` Atelier Nord | $15,000.00 | $13,300.20 | $12,800.00 | $-500.20 | `SETTLEMENT_VARIANCE_EXCEPTION` |
| `MRC-OK-01` Verified Goods | $10,000.00 | $8,210.00 | $8,500.00 | $+290.00 | `SETTLEMENT_VARIANCE_EXCEPTION` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Payout Settlement Reconciliation` routine via `schedule_task`:

```text
Schedule recurring job "Daily Payout Settlement Reconciliation" on cron `15 4 * * *` (`UTC`) with instruction: "Run daily merchant payout vs PSP bank settlement reconciliation via scripts/payout_ledger_reconciler.py and escalate negative clawback balances before bank cutoff."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `merchant_payouts`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `merchant_payouts` requires [`merchant_id`; `gross_gmv_local`; `actual_psp_settled_amount` or `actual_psp_settled`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `default_commission_rate_pct` | `number` | `15.0` | Standard marketplace take-rate percentage. |
| `settlement_variance_tolerance_usd` | `number` | `5.0` | Materiality tolerance between expected net payout and PSP wire. |

See [`../../README.md`](../../README.md) for the `marketplace-superapp-ops` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
