# Merchandising Promo Lift & Margin ROI (`merchandising-assortment-planner`)

Computes promotional unit and revenue lift normalized by campaign duration, adjusts for sibling SKU cannibalization, basket halo, and vendor coop funding, and calculates net margin ROI. Deterministic computation executes via [`scripts/promo_lift_analyzer.py`](scripts/promo_lift_analyzer.py). Domain guards enforced: Normalizes multi-week baseline to exact promo_days before lift calculation; Deducts sibling cannibalization and promo execution cost cleanly. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Category Merchandising Manager**: Triggered when evaluating seasonal promotional lift, halo margin, and markdown plans; models net incremental gross margin after discount subsidy and cannibalization (`>0.15` ROI floor).
- **Retail Pricing & Planning Analyst**: Triggered when auditing margin-destructive markdown or promo campaigns prior to renewal; quantifies net margin leakage (`-$350` to `-$45k` losses) hidden behind top-line unit volume gains.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`merchandising-assortment-planner.zip`](../../../../dist/skills/merchandising-assortment-planner.zip) (or the full department bundle [`retail-store-merchandising.zip`](../../../../dist/bundles/retail-store-merchandising.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP Retail ERP & POS Store Telemetry MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/merchandising-assortment-planner` or `@merchandising-assortment-planner`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.promo_lift_analyzer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"campaigns": [{"campaign_id": r.get("Custom campaign_id"), "baseline_units": r.get("Custom baseline_units"), "promo_units": r.get("Custom promo_units")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/retail-store-merchandising/skills/merchandising-assortment-planner/scripts/promo_lift_analyzer.py \
  --input examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx \
  --config plugins/retail-store-merchandising/skills/merchandising-assortment-planner/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `promo_lift_analyzer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` + Customer BYO-MCP (`SAP Retail ERP & POS Store Telemetry MCP server`) via `remote_cli mcp`):** "Evaluate Northstar Retail 7-day beverage promo with $18k cannibalization loss and $12k media spend against 28-day baseline."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Merchandising Promo Sheet with vendor coop funding and cross-category basket halo."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx) and ask: "Evaluate the seasonal retail promotions in `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` using net incremental gross margin—factoring in markdown subsidy, basket halo, and category cannibalization—to expose unprofitable volume-driven promos."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `2` retail campaigns in `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` shows **`$-350.00` net portfolio incremental gross margin**: loyalty promo **`PROMO-SNK-15` generated `+$3,450.00` net margin (`8.62x` ROI, `PROFITABLE_SCALE`)**, whereas **`PROMO-BEV-50` (`+180%` unit lift) destroyed `-$3,800.00` in net margin (`-2.53x` ROI)** via `-$1,800.00` cannibalization.

- **Scale Winner (`PROMO-SNK-15`):** `+110.0%` unit lift plus `$950.00` halo margin easily outweighed `-$200.00` cannibalization (`+$3,450.00` net).
- **Value-Destructive Trap (`PROMO-BEV-50`):** Deep `50%`-off discounting drove `+180.0%` top-line units yet lost `-$800.00` direct margin and `-$1,800.00` cannibalization (`MARGIN_DESTRUCTIVE`).
- **Approval Confirmation Prompt:** Discontinue `PROMO-BEV-50` ahead of next cycle and confirm before recording any associated promo inventory adjustments or vendor coop debits via your connected ERP MCP server (gated by `Auto-Guardian`) / your connected AP / ERP MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx`](../../../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx) (`133.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Promotional Lift, Cannibalization & Net Margin Attribution

- **Campaigns:** 2 | **Profitable:** 1 | **Margin Destructive:** 1 | **Portfolio Net Incremental GM:** $-350.00

| Campaign | Unit Lift | Direct Inc GM | Halo GM | Cannibalization | Net Inc GM | ROI | Verdict |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `PROMO-SNK-15` Artisan Grain 15% Loyalty | +110.0% | $1,900.00 | $950.00 | -$200.00 | $3,450.00 | 8.62x | `PROFITABLE_SCALE` |
| `PROMO-BEV-50` Sparkling Hydration 50% Off | +180.0% | $-800.00 | $300.00 | -$1,800.00 | $-3,800.00 | -2.53x | `MARGIN_DESTRUCTIVE` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily Store Shrink & Zero-Scan Watch` routine via `schedule_task`:

```text
Schedule recurring job "Daily Store Shrink & Zero-Scan Watch" on cron `30 6 * * *` (`UTC`) with instruction: "Run the morning store shrink and zero-scan phantom inventory sweep via scripts/store_shrink_task_ranker.py and produce prioritized cycle-count lists per store manager."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `campaigns`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `campaigns` requires [`campaign_id` or `campaign_name`; `baseline_units` or `baseline_revenue_usd`; `promo_units` or `promo_revenue_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_acceptable_promo_roi` | `number` | `0.15` | Minimum incremental net gross margin ROI ratio to classify campaign as scalable. |

See [`../../README.md`](../../README.md) for the `retail-store-merchandising` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
