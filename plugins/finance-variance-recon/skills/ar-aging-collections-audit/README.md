# AR Aging & Collections Audit (`ar-aging-collections-audit`)

Classifies open accounts receivable across Current, 1-30, 31-60, 61-90, and 90+ day buckets while strictly isolating negative credit memos so credits never mask delinquent exposure, computes DSO, and ranks collections priority. Deterministic computation executes via [`scripts/aging_bucket_auditor.py`](scripts/aging_bucket_auditor.py). Domain guards enforced: Isolates negative invoices and CREDIT_MEMO rows so credits never hide 90+ overdue exposure; Uses consistent trailing 90-day credit sales denominator for DSO. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Order-to-Cash (O2C) Credit Manager**: Triggered when prioritizing collections worklists and calculating clean DSO ahead of close; isolates negative unapplied credit memos (`-$18,500`) so they never net out `90+` day delinquent receivables.
- **Treasury & Working Capital Analyst**: Triggered when forecasting bad-debt reserve exposure across disputed and aged invoices; triggers formal collections escalation on customers exceeding `$10,000` in `90+` day aging.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`ar-aging-collections-audit.zip`](../../../../dist/skills/ar-aging-collections-audit.zip) (or the full department bundle [`finance-variance-recon.zip`](../../../../dist/bundles/finance-variance-recon.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/ar-aging-collections-audit` or `@ar-aging-collections-audit`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.aging_bucket_auditor import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"open_items": [{"customer_id": r.get("Custom customer_id"), "open_amount_usd": r.get("Custom open_amount_usd"), "due_date": r.get("Custom due_date")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/finance-variance-recon/skills/ar-aging-collections-audit/scripts/aging_bucket_auditor.py \
  --input examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx \
  --config plugins/finance-variance-recon/skills/ar-aging-collections-audit/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `aging_bucket_auditor.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`SAP S/4HANA / Oracle ERP MCP server`) via `remote_cli mcp`):** "Audit Veloce SuperApp's open AR subledger where a major customer has a $45k `90+` invoice alongside a `-40k` credit memo."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Compute DSO and bucket totals from our Drive AR Aging Sheet using trailing 90-day credit sales."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx) and ask: "Audit the open Accounts Receivable subledger in `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` as of `2026-11-10`, isolate negative unapplied credit memos so they don't mask `90+` day delinquencies, compute DSO, and rank collections escalation targets."

## Sample Response

### What You See in Gemini Enterprise Chat

Reconciling `4` open customer balances in `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` shows **`$692,000.00` gross positive AR** (`$673,500.00` net after isolating **`-$18,500.00` in unapplied credits**), **`$435,000.00` (`62.9%`) in the `90+` day bucket**, `3.4`-day DSO on sample credit sales, and **`2` customers breaching collections escalation thresholds**.

- **Immediate Escalations (`$435,000.00` `90+`d):** `Kestrel Logistics Ltd` (`CUST-002`, `$290,000.00` at `90+`d) and `Cymbal Retail Corp` (`CUST-001`, `$145,000.00` at `90+`d with `-$18,500.00` unapplied credit isolated rather than netted) exceed threshold.
- **Current / Early Buckets (`1-30d`):** `Nordic Telecom ASA` (`$165,000.00`) and `Meridian Financial` (`$92,000.00`) remain within early `1-30` day terms.
- **Approval Confirmation Prompt:** Confirm if you would like to dispatch formal dunning notices to `Kestrel Logistics Ltd` and `Cymbal Retail Corp` via your connected `Gmail` or `Outlook` connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx`](../../../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx) (`149.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Accounts Receivable Aging & Collections Audit (As Of 2026-11-10)

- **Gross Positive AR:** $692,000.00 | **Isolated Unapplied Credits:** $-18,500.00 | **Net AR:** $673,500.00
- **Buckets:** Current $0.00 | 1-30d $257,000.00 | 31-60d $0.00 | 61-90d $0.00 | **90+d $435,000.00**
- **DSO:** 3.4 days | **Escalation Customers (>= threshold):** 2

| Customer | Gross AR | Current | 1-30d | 31-60d | 61-90d | 90+d | Unapplied Credits | Escalate |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `CUST-002` Kestrel Logistics Ltd | $290,000.00 | $0.00 | $0.00 | $0.00 | $0.00 | **$290,000.00** | $0.00 | YES |
| `CUST-001` Cymbal Retail Corp | $145,000.00 | $0.00 | $0.00 | $0.00 | $0.00 | **$145,000.00** | $-18,500.00 | YES |
| `CUST-004` Nordic Telecom ASA | $165,000.00 | $0.00 | $165,000.00 | $0.00 | $0.00 | **$0.00** | $0.00 | No |
| `CUST-003` Meridian Financial | $92,000.00 | $0.00 | $92,000.00 | $0.00 | $0.00 | **$0.00** | $0.00 | No |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily AP & GR/IR Exception Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily AP & GR/IR Exception Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the weekday morning AP 3-way match sweep using scripts/reconcile_3way.py across open vendor invoices, purchase orders, and goods receipts. Surface duplicate invoice suspects, bank-change holds, TCURX decimal mismatches, and price/quantity exceptions for AP Controller review without releasing payments."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `trailing_90d_credit_sales_usd`, `open_items`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `open_items` requires [`customer_id` or `customer_name`; `open_amount_usd`; `due_date`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `ar_escalation_90_plus_threshold` | `number` | `10000.0` | 90+ days past due customer balance threshold triggering formal collections escalation. |

See [`../../README.md`](../../README.md) for the `finance-variance-recon` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
