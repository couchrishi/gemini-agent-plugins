# P&L Budget Variance Bridge (`pnl-budget-variance-bridge`)

Computes P&L Actual vs Budget and Forecast variance bridges decomposed into constant-FX volume/rate vs FX translation impact, enforces leaf-vs-parent GL hierarchy tie-outs to prevent double-counting, and flags materiality breaches. Deterministic computation executes via [`scripts/pnl_variance_engine.py`](scripts/pnl_variance_engine.py). Domain guards enforced: Excludes summary rollup rows from consolidated EBITDA sums and verifies leaf tie-out; Inverts favorability direction between revenue and expense categories. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Corporate FP&A Controller**: Triggered when bridging Q3/FY actuals vs budget across hierarchical general ledger extracts; excludes parent subtotal rows (`REV-TOT`, `OPEX-TOT`) so revenue never double-counts, and splits constant-currency vs FX variance.
- **Business Unit Finance Partner**: Triggered when diagnosing cost overruns vs favorable FX tailwinds across EMEA/APAC/AMER; inverts cost favorability polarity cleanly and reports material line variances (`>$25k` / `>10%`).

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`pnl-budget-variance-bridge.zip`](../../../../dist/skills/pnl-budget-variance-bridge.zip) (or the full department bundle [`finance-variance-recon.zip`](../../../../dist/bundles/finance-variance-recon.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/pnl-budget-variance-bridge` or `@pnl-budget-variance-bridge`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.pnl_variance_engine import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"lines": [{"account_id": r.get("Custom account_id"), "actual_local": r.get("Custom actual_local"), "budget_local": r.get("Custom budget_local")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/finance-variance-recon/skills/pnl-budget-variance-bridge/scripts/pnl_variance_engine.py \
  --input examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx \
  --config plugins/finance-variance-recon/skills/pnl-budget-variance-bridge/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `pnl_variance_engine.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP MCP server`) via `remote_cli mcp`):** "Build the Northstar Retail Q3 P&L constant-currency variance bridge from BigQuery GL actuals containing both parent rollup and leaf rows."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Bridge EMEA software revenue and cloud COGS variance from our Finance Close Sheet using actual vs budget FX rates."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx) and ask: "Build a constant-currency P&L variance bridge from the attached `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` workbook, excluding parent rollup subtotal rows from GL sums, verifying hierarchy tie-outs, and splitting operational performance from FX swings."

## Sample Response

### What You See in Gemini Enterprise Chat

Excluding `2` parent summary rollup lines (`1` hierarchy tie-out discrepancy flagged) across `6` leaf GL accounts in `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`, **actual revenue reached `$42,500,000.00` vs. `$40,484,000.00` budget** and **actual EBITDA reached `$24,080,000.00` (`+$496,000.00` net favorable variance)**.

- **Revenue Constant-FX vs. Currency Drag:** `4100` Cloud Platform US beat budget (`+$1,700,000`), while `4200` EMEA (`+$560k` operational, `-$700k` FX -> `-$140k` net) and `4300` APAC (`+$816k` operational, `-$360k` FX -> `+$456k` net) absorbed `-1,060,000` USD in currency headwinds.
- **Cost Variance Directionality:** `6100` Cloud Compute & GPU (`+$1,650k` unfavorable) drove OpEx pressure partially offset by `6200` EMEA Payroll (`-$252k` favorable net of `-$364k` FX).
- **Approval Confirmation Prompt:** Confirm if you would like to route any vendor payment adjustments or GL close annotations via your connected ERP MCP server (`Auto-Guardian` confirmation required) (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx) (`146.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# P&L Budget vs. Actual Constant-Currency Variance Bridge

- **Actual Revenue:** $42,500,000.00 vs **Budget:** $40,484,000.00
- **Actual EBITDA:** $24,080,000.00 vs **Budget EBITDA:** $23,584,000.00 (**Bridge:** $+496,000.00)
- **Leaf Accounts:** 6 | **Parent Summary Rows Isolated:** 2 | **Hierarchy Tie-Out Breaks:** 1

| Account | Category | Actual | Budget | Var ($) | Const-FX ($) | FX ($) | Direction | Material |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |
| `4100` Cloud Platform Subscriptions (US) | revenue | $24,200,000.00 | $22,500,000.00 | $+1,700,000.00 | $+1,700,000.00 | $+0.00 | FAVORABLE | YES |
| `4200` Enterprise Subscriptions (EMEA) | revenue | $10,500,000.00 | $10,640,000.00 | $-140,000.00 | $+560,000.00 | $-700,000.00 | UNFAVORABLE | YES |
| `4300` APAC Digital Subscriptions (JP) | revenue | $7,800,000.00 | $7,344,000.00 | $+456,000.00 | $+816,000.00 | $-360,000.00 | FAVORABLE | YES |
| `6100` Cloud Compute & GPU Infrastructure | opex | $7,850,000.00 | $6,200,000.00 | $+1,650,000.00 | $+1,650,000.00 | $+0.00 | UNFAVORABLE | YES |
| `6200` Field Engineering Payroll (EMEA) | opex | $5,460,000.00 | $5,712,000.00 | $-252,000.00 | $+112,000.00 | $-364,000.00 | FAVORABLE | YES |
| `6300` Enterprise GTM & Events | opex | $5,110,000.00 | $4,988,000.00 | $+122,000.00 | $+122,000.00 | $+0.00 | UNFAVORABLE | YES |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily AP & GR/IR Exception Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily AP & GR/IR Exception Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the weekday morning AP 3-way match sweep using scripts/reconcile_3way.py across open vendor invoices, purchase orders, and goods receipts. Surface duplicate invoice suspects, bank-change holds, TCURX decimal mismatches, and price/quantity exceptions for AP Controller review without releasing payments."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `lines`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `lines` requires [`account_id` or `account_name`; `actual_local` or `actual_usd` or `actual`; `budget_local` or `budget_usd` or `budget`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `default_currency` | `string` | `USD` | Reporting presentation currency ISO-4217 code. |
| `materiality_amount_threshold` | `number` | `25000.0` | Absolute variance threshold in reporting currency. |
| `materiality_pct_threshold` | `number` | `10.0` | Relative percentage variance materiality threshold. |
| `hierarchy_tolerance_amount` | `number` | `1.0` | Maximum allowed rounding delta between GL parent summary totals and sum of leaf lines. |

See [`../../README.md`](../../README.md) for the `finance-variance-recon` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
