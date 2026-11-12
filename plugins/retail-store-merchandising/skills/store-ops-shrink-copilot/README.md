# Store Shrink, Phantom Inventory & Associate Tasks (`store-ops-shrink-copilot`)

Quantifies store shrink variance, detects zero-scan phantom inventory and negative inventory corruption while filtering out unpolled POS terminals, and prioritizes associate tasks. Deterministic computation executes via [`scripts/store_shrink_task_ranker.py`](scripts/store_shrink_task_ranker.py). Domain guards enforced: Skips non-POLLED POS stores accurately instead of generating phantom flags; Separates negative book qty ledger corruption from physical theft shrink. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Regional Loss Prevention & Inventory Lead**: Triggered when investigating suspected store shrink vs reporting outages across multi-store POS feeds; excludes `MISSING` POS poll stores before attributing shrinkage, deducts phantom inventory (`>=4` book qty, `>=5d` zero scan), and ranks store tasks.
- **District Store Operations Manager**: Triggered when dispatching morning cycle-count and EAS tag checks without false store blame; separates physical theft variances (`>$250`) from silent POS data-sync failures.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`store-ops-shrink-copilot.zip`](../../../../dist/skills/store-ops-shrink-copilot.zip) (or the full department bundle [`retail-store-merchandising.zip`](../../../../dist/bundles/retail-store-merchandising.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP Retail ERP & POS Store Telemetry MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/store-ops-shrink-copilot` or `@store-ops-shrink-copilot`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.store_shrink_task_ranker import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"sku_store_records": [{"store_id": r.get("Custom store_id"), "sku": r.get("Custom sku"), "book_on_hand_qty": r.get("Custom book_on_hand_qty")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/retail-store-merchandising/skills/store-ops-shrink-copilot/scripts/store_shrink_task_ranker.py \
  --input examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx \
  --config plugins/retail-store-merchandising/skills/store-ops-shrink-copilot/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `store_shrink_task_ranker.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP Retail ERP & POS Store Telemetry MCP server`) via `remote_cli mcp`):** "Analyze Northstar Retail store SKU snapshot where STR-104 has 18 units on hand with 7 zero-scan days and STR-109 has MISSING POS poll."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit Store Cycle-Count Sheet in Drive for physical shrink > $250 and negative book counts."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx) and ask: "Audit the store inventory and POS sync tabs in `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` to separate genuine physical shrink and zero-scan phantom inventory (`>=4` book qty, `>=5d` zero sales) from stores experiencing unpolled POS outages."

## Sample Response

### What You See in Gemini Enterprise Chat

Scanning `3` retail store records in `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` calculated **`$2,885.00` total physical shrink**, **`1` phantom zero-scan alert (`STR-104` `SKU-901-ANC` Apex Pro ANC Headphones, `24` book units, `9` zero-scan days, `$2,800.00`)**, and **cleanly excluded `1` unpolled POS outage store** so associate tasks target real discrepancies only.

- **Priority Task #1 (`STR-104` / `SKU-901-ANC`):** `24` units on book with `9` consecutive zero-scan days (`$2,800.00` value) queued for immediate physical shelf walk and backroom audit.
- **POS Outage False-Alarm Prevention:** Excluded `1` `MISSING` POS poll store before computing phantom-inventory task lists (`unpolled_pos_skipped: 1`).
- **Approval Confirmation Prompt:** Confirm store physical recount completion before posting any `$2,885.00` inventory adjustment write-offs via your connected ERP MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx) (`135.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Store Shrink, Phantom Inventory & Associate Task Plan

- **Stores:** 3 | **Total Physical Shrink:** $2,885.00 | **Phantom Inventory (Zero-Scan):** 1 | **Negative Ledger:** 0

> Skipped 1 record(s) with non-POLLED POS status to prevent false phantom-inventory flags.

| Priority | Store | SKU | Anomaly Type | Book Qty | Zero-Scan Days | Shrink $ | Action |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- |
| 1 | `STR-104` | `SKU-901-ANC` Apex Pro ANC Headphones | `PHANTOM_INVENTORY_ZERO_SCAN` | 24 | 9 | $2,800.00 | Execute shelf physical walk + backroom pull or zero-out PI |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Store Shrink & Zero-Scan Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Store Shrink & Zero-Scan Watch" on cron `30 6 * * *` (`UTC`) with instruction: "Run the morning store shrink and zero-scan phantom inventory sweep via scripts/store_shrink_task_ranker.py and produce prioritized cycle-count lists per store manager."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `sku_store_records`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `sku_store_records` requires [`store_id`; `sku`; `book_on_hand_qty`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `zero_scan_days_threshold` | `integer` | `5` | Days without POS scans for positive book on-hand before flagging phantom inventory. |
| `min_book_qty_for_phantom` | `integer` | `4` | Minimum perpetual book qty required to trigger zero-scan investigation. |
| `high_shrink_usd_threshold` | `number` | `250.0` | Physical count variance threshold in USD triggering EAS/receiving audit. |

See [`../../README.md`](../../README.md) for the `retail-store-merchandising` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
