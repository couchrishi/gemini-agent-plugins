# GR/IR Clearing Orchestrator (`gr-ir-clearing-orchestrator`)

Reconciles goods receipt vs invoice receipt clearing imbalances across SAP PO lines with TCURX decimal normalization, SHKZG reversals, and aging threshold flags. Deterministic computation executes via [`scripts/gr_ir_reconciler.py`](scripts/gr_ir_reconciler.py). Domain guards enforced: Applies TCURX decimal scaling and SHKZG='H' credit reversal; Flags open imbalances older than 60 days as aging_breach=true. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **SAP Materials Management / Close Accountant**: Triggered when reconciling aged Goods Receipt / Invoice Receipt (`WRX` / `F.13` / `MR11`) suspense balances; normalizes `TCURX` JPY decimals, separates GR-without-IR (`PO-GRIR-JP-2410`) from IR-without-GR (`PO-GRIR-US-2560`), and stages write-offs.
- **Procurement Operations Controller**: Triggered when quantifying aged `>60`-day accrued liabilities before month-end close; routes imbalanced clearing batches through strict controller approval before posting SAP MR11 entries.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`gr-ir-clearing-orchestrator.zip`](../../../../dist/skills/gr-ir-clearing-orchestrator.zip) (or the full department bundle [`erp-procure-to-pay.zip`](../../../../dist/bundles/erp-procure-to-pay.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP & PLM BOM MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/gr-ir-clearing-orchestrator` or `@gr-ir-clearing-orchestrator`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.gr_ir_reconciler import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"gr_ir_postings": [{"po_number": r.get("Custom po_number"), "gr_amount": r.get("Custom gr_amount")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/erp-procure-to-pay/skills/gr-ir-clearing-orchestrator/scripts/gr_ir_reconciler.py \
  --input examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx \
  --config plugins/erp-procure-to-pay/skills/gr-ir-clearing-orchestrator/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `gr_ir_reconciler.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP & PLM BOM MCP server`) via `remote_cli mcp`):** "Reconcile Apex Manufacturing SAP EKBE GR/IR lines including JPY raw postings and SHKZG='H' reversals."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check our Drive GR/IR Aging Sheet as of 2026-11-10 for accruals open > 60 days."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx) and ask: "Reconcile the SAP Goods Receipt / Invoice Receipt (`GR/IR`) suspense tabs in `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` as of `2026-11-10`, separating `GR-without-IR` accrued liabilities from `IR-without-GR` payment blocks and flagging >60-day aging breaches."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `3` PO lines in `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` as of `2026-11-10`, **`1` line (`PO-GRIR-00003`, `$0.00` balance, `13d`) is eligible to clear**, while **`2` aged `>60d` open imbalances (`$21,000.00` gross imbalance)** split cleanly into `1` GR-without-IR (`PO-GRIR-JP-2410`) and `1` IR-without-GR (`PO-GRIR-US-2560`).

- **Accrued Liability Kept (`PO-GRIR-JP-2410`, `V-TOKYO-PRECISION`, `128d`):** `GR_WITHOUT_IR` of `+120.00` units (`+$12,000.00`) — maintain GR/IR accrual and chase missing vendor invoice.
- **Blocked AP Payment (`PO-GRIR-US-2560`, `V-PACIFIC-LOG`, `113d`):** `IR_WITHOUT_GR` of `-60.00` units (`-$9,000.00`) — hold AP disbursement and verify physical dock receipt or demand credit memo.
- **Approval Confirmation Prompt:** Confirm if you would like to clear only `PO-GRIR-00003` (`$0.00`) via your connected ERP MCP server (`Auto-Guardian` confirmation required) while holding `PO-GRIR-JP-2410` and `PO-GRIR-US-2560` out of MR11 write-offs.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx`](../../../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx) (`138.0 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# SAP GR/IR Clearing Reconciliation (As Of 2026-11-10)

- **PO Lines:** 3 | **Open Imbalances:** 2 | **GR w/o IR:** 1 | **IR w/o GR:** 1
- **Aging Breaches (> limit):** 2 | **Gross Imbalance:** $21,000.00

| PO | Line | Vendor | Net Qty | Net Imbalance (USD) | Age (d) | State | Action |
| :--- | :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `PO-GRIR-00003` | `10` | `V-CORE-1` | +0.00 | $+0.00 | 13 | `BALANCED_CLEARED` | Auto-clear via MR11/F.13 (eligible) |
| `PO-GRIR-JP-2410` | `10` | `V-TOKYO-PRECISION` | +120.00 | $+12,000.00 | 128 | `GR_WITHOUT_IR` | Maintain accrued GR/IR liability; chase vendor invoice |
| `PO-GRIR-US-2560` | `10` | `V-PACIFIC-LOG` | -60.00 | $-9,000.00 | 113 | `IR_WITHOUT_GR` | Block AP payment; confirm physical goods receipt or credit memo |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily GR/IR Aging Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily GR/IR Aging Watch" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Execute weekday SAP GR/IR clearing aging check via scripts/gr_ir_reconciler.py to isolate IR_WITHOUT_GR blocks and >60 day accruals."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `fx_rates`, `decimal_places`, `gr_ir_postings`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `gr_ir_postings` requires [`po_number`; `gr_amount` or `ir_amount` or `gr_qty` or `ir_qty` or `amount`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `default_currency` | `string` | `USD` | Presentation currency code. |
| `gr_ir_aging_threshold_days` | `integer` | `60` | Aging threshold in days for open GR/IR write-off review. |
| `clearing_tolerance_usd` | `number` | `5.0` | Residual value tolerance for automated MR11/F.13 clearing proposals. |

See [`../../README.md`](../../README.md) for the `erp-procure-to-pay` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
