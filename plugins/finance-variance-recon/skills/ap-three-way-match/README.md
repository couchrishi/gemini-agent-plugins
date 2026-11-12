# AP Three-Way Match (`ap-three-way-match`)

Performs deterministic PO/Goods Receipt/Invoice 3-way matching, normalizes SAP TCURX zero-decimal currencies and SHKZG credit signs, flags duplicate invoices and bank-change fraud alerts, and holds exceptions before ERP posting. Deterministic computation executes via [`scripts/reconcile_3way.py`](scripts/reconcile_3way.py). Domain guards enforced: Applies TCURX decimal factor (100x JPY/KRW, 0.1x KWD) when sap_raw_encoding is true; Treats SAP SHKZG='H' lines as credits and holds missing GRNs. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **AP Controller / Shared Services Lead**: Triggered when reconciling SAP S/4HANA or Oracle purchase orders, goods receipts, and vendor invoices; applies `TCURX` zero/three-decimal FX scaling (`JPY x100`), reverses `SHKZG='H'` credits, and holds fuzzy/exact duplicates and bank fraud.
- **Disbursement Audit Analyst**: Triggered when clearing payment runs before releasing ACH/wire batches; blocks price (`>2%` / `$500`) or quantity over-billings and vendor bank-account mismatches.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`ap-three-way-match.zip`](../../../../dist/skills/ap-three-way-match.zip) (or the full department bundle [`finance-variance-recon.zip`](../../../../dist/bundles/finance-variance-recon.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/ap-three-way-match` or `@ap-three-way-match`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.reconcile_3way import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"purchase_orders": [{"po_number": r.get("Custom po_number"), "ordered_qty": r.get("Custom ordered_qty"), "unit_price": r.get("Custom unit_price")} for r in wb["Source_Tab"]], "goods_receipts": wb["goods_receipts"], "invoices": wb["invoices"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/finance-variance-recon/skills/ap-three-way-match/scripts/reconcile_3way.py \
  --input examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx \
  --config plugins/finance-variance-recon/skills/ap-three-way-match/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `reconcile_3way.py`: `--po`, `--gr`, `--invoice`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP MCP server`) via `remote_cli mcp`):** "Run AP 3-way match on Apex Manufacturing's JPY and USD invoices from SAP OData."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit our Drive AP Exception Sheet where a vendor submitted a same-amount duplicate invoice and a Gmail bank account change."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx) and ask: "Using the attached `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` workbook, run a 3-way match across purchase orders, goods receipts, and vendor invoices, normalize SAP `TCURX` zero-decimal currencies and `SHKZG` credit memos, and separate invoices ready to pay from fraud, duplicate, or quantity holds."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `7` vendor invoices in `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`, **`3` invoices totaling `$20,730.00` (`INV-APX-JP-1842` scaled via `TCURX` JPY x100 to `$10,000.00`, `INV-APX-1001`, and `INV-APX-1002`) passed full 3-way matching**, **`1` SAP `SHKZG='H'` credit memo (`INV-APX-CR-2140`, `-$6,200.00`)** was normalized cleanly, and **`3` exception invoices totaling `$24,400.00`** are held.

- **Duplicate & Price Blocks (`2` invoices, `$12,400.00`):** `INV-APX-US-1915` and `INV-APX-US-1915-DUP` (`V-CLOUD-INFRA`, `$6,200.00` each) tripped both fuzzy/exact duplicate guards and a `+24.00%` (`$1,200`) price breach over PO limits.
- **Quantity Over-Billing Hold (`1` invoice, `$12,000.00`):** `INV-APX-QTY-2280` (`V-PACIFIC-LOG`) billed `100.0` units against only `80.0` ordered/received.
- **Approval Confirmation Prompt:** Confirm if you would like to release the `3` matched invoices (`$20,730.00`) via your connected ERP MCP server (`Auto-Guardian` confirmation required). The `3` held exceptions (`$24,400.00`) remain blocked pending vendor dispute resolution.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx) (`151.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# AP 3-Way Match Reconciliation Report

- **Invoices Evaluated:** 7 | **Matched:** 3 | **Held Exceptions:** 3 (Fraud/Duplicate: 2)
- **Matched Value:** $20,730.00 | **Held Value:** $24,400.00

| Invoice | Vendor | PO | Currency | Amount (USD) | Status | Exceptions |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- |
| `INV-APX-JP-1842` | `V-TOKYO-PRECISION` | `PO-APX-JP-901` | JPY | $10,000.00 | `MATCHED_READY_FOR_HITL` | Clean 3-way match |
| `INV-APX-US-1915` | `V-CLOUD-INFRA` | `PO-APX-US-902` | USD | $6,200.00 | `DUPLICATE_BLOCK` | DUPLICATE_SUSPECT_FUZZY: Same vendor/amount within 3d of INV-APX-US-1915-DUP.; PRICE_VARIANCE: Delta $1,200.00 (24.00%) breaches tolerance (2.0% / $500). |
| `INV-APX-US-1915-DUP` | `V-CLOUD-INFRA` | `PO-APX-US-902` | USD | $6,200.00 | `DUPLICATE_BLOCK` | DUPLICATE_SUSPECT_EXACT: Matches INV-APX-US-1915 on vendor+invoice_number.; PRICE_VARIANCE: Delta $1,200.00 (24.00%) breaches tolerance (2.0% / $500). |
| `INV-APX-CR-2140` | `V-CLOUD-INFRA` | `PO-APX-US-902` | USD | $-6,200.00 | `CREDIT_MEMO_POSTED` | SAP SHKZG='H' credit memo normalized cleanly. |
| `INV-APX-QTY-2280` | `V-PACIFIC-LOG` | `PO-APX-QTY-903` | USD | $12,000.00 | `EXCEPTION_HOLD` | QTY_VARIANCE: Invoiced 100.0 exceeds received/ordered 80.0. |
| `INV-APX-1001` | `V-SYNTH-CNC` | `PO-APX-1001` | USD | $3,800.00 | `MATCHED_READY_FOR_HITL` | Clean 3-way match |
| `INV-APX-1002` | `V-EURO-PACK` | `PO-APX-1002` | EUR | $6,930.00 | `MATCHED_READY_FOR_HITL` | Clean 3-way match |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily AP & GR/IR Exception Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily AP & GR/IR Exception Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the weekday morning AP 3-way match sweep using scripts/reconcile_3way.py across open vendor invoices, purchase orders, and goods receipts. Surface duplicate invoice suspects, bank-change holds, TCURX decimal mismatches, and price/quantity exceptions for AP Controller review without releasing payments."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `fx_rates`, `decimal_places`, `purchase_orders`, `goods_receipts`, `invoices`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `purchase_orders` requires [`po_number`; `ordered_qty` or `quantity` or `qty`; `unit_price` or `amount`] | `goods_receipts` requires [`po_number`; `received_qty` or `quantity` or `qty`] | `invoices` requires [`po_number`; `invoice_id` or `invoice_number`; `unit_price` or `amount`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `default_currency` | `string` | `USD` | Reporting presentation currency ISO-4217 code. |
| `price_tolerance_pct` | `number` | `0.02` | AP 3-way match unit price tolerance fraction (e.g., 0.02 = 2%). |
| `price_tolerance_abs` | `number` | `500.0` | Hard dollar cap per invoice line above which AP Manager approval is required regardless of %. |
| `qty_tolerance_pct` | `number` | `0.0` | Allowed over-bill / over-receipt tolerance fraction. |
| `duplicate_date_window_days` | `integer` | `3` | Date window in days for fuzzy vendor/amount duplicate invoice detection. |

See [`../../README.md`](../../README.md) for the `finance-variance-recon` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
