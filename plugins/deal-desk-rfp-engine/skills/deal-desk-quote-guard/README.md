# Deal Desk Quote Guard (`deal-desk-quote-guard`)

Validates multi-year SaaS quotes and ramp schedules for net effective discount, Year-1 vs blended ACV, TCV, gross margin floors, and non-standard terms. Deterministic computation executes via [`scripts/deal_margin_validator.py`](scripts/deal_margin_validator.py). Domain guards enforced: Separates Year-1 ACV from blended multi-year ACV on ramped schedules; Routes margin breaches and non-standard payment/SLA terms to Tier 3 CFO Desk. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Deal Desk Manager**: Triggered when auditing quarter-end enterprise quotes with non-standard Net-90 terms or high discounts; routes quotes crossing discount (`>35%`) or gross-margin floors cleanly to Tier-2 Deal Desk or Tier-3 CFO.
- **Finance Commercial Controller**: Triggered when validating blended hardware/software/services margin before countersigning; quantifies net TCV impact and non-standard termination-for-convenience (TfC) exposure.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`deal-desk-quote-guard.zip`](../../../../dist/skills/deal-desk-quote-guard.zip) (or the full department bundle [`deal-desk-rfp-engine.zip`](../../../../dist/bundles/deal-desk-rfp-engine.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/deal-desk-quote-guard` or `@deal-desk-quote-guard`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.deal_margin_validator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"quotes": [{"quote_id": r.get("Custom quote_id"), "customer_name": r.get("Custom customer_name")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/deal-desk-rfp-engine/skills/deal-desk-quote-guard/scripts/deal_margin_validator.py \
  --input examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx \
  --config plugins/deal-desk-rfp-engine/skills/deal-desk-quote-guard/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `deal_margin_validator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail` via `remote_cli mcp`):** "Evaluate Northstar Retail's 3-year ramped Salesforce quote (Y1 $80k, Y2 $180k, Y3 $260k) with Net 60 payment terms."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check our Deal Desk Pricing Sheet in Drive for Apex Manufacturing where blended margin dropped to 56%."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx) and ask: "Audit the enterprise software quotes in `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` for ramped vs. blended ACV, non-standard SLA credits or termination clauses, discount tier routing, and gross-margin floor compliance."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `3` enterprise quotes totaling **`$1,476,000.00` Net TCV** in `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` flagged **`1` Tier-3 CFO escalation (`QUO-APX-4418` for Cymbal Financial Group)** due to `38.3%` discounting and `56.7%` gross margin violating the margin floor.

- **Tier-3 Escalation Required (`QUO-APX-4418`):** `$852,000.00` Net TCV (`$284,000/yr` ACV) with `38.3%` discount and `56.7%` gross margin routes directly to **Tier 3: CFO / Executive Desk**.
- **Standard Routing (`QUO-APX-4001` & `QUO-APX-4002`):** Meridian Logistics (`$264k` Net TCV, `12.0%` disc, `75.0%` GM) qualifies as `Tier 0: Auto-Approved`, and Northstar Retail (`$360k` Net TCV, `20.0%` disc, `72.5%` GM) routes to **Tier 1: Regional Sales VP**.
- **Approval Confirmation Prompt:** Confirm if you want to submit `QUO-APX-4418` to executive review via your connected Deal Desk / `Salesforce` approval connector (gated by `Auto-Guardian`) and update quote status via your connected `Salesforce` connector.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx) (`143.6 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Deal Desk Quote & Margin Guard

- **Quotes Evaluated:** 3 | **Total Net TCV:** $1,476,000.00
- **Tier-3 Escalations:** 1 | **Margin Floor Breaches:** 1

| Quote | Customer | Net TCV | Y1 ACV | Blended ACV | Discount % | Gross Margin % | Approval Tier |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `QUO-APX-4418` | Cymbal Financial Group | $852,000.00 | $284,000.00 | $284,000.00 | 38.3% | 56.7% | Tier 3: CFO / Executive Desk |
| `QUO-APX-4001` | Meridian Logistics | $264,000.00 | $88,000.00 | $88,000.00 | 12.0% | 75.0% | Tier 0: Auto-Approved |
| `QUO-APX-4002` | Northstar Retail | $360,000.00 | $120,000.00 | $120,000.00 | 20.0% | 72.5% | Tier 1: Regional Sales VP |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Pipeline Hygiene Audit` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Pipeline Hygiene Audit" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly Salesforce pipeline hygiene and slippage audit using scripts/pipeline_slippage_auditor.py. Normalize multi-currency opportunities, identify stale stages, >=2 push-count deals, single-threaded Commit opportunities, and StageName/IsClosed inconsistencies without modifying CRM records autonomously."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `quote_id`, `customer_name`, `term_months`, `payment_terms_days`, `billing_frequency`, `termination_for_convenience`, `line_items`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `quotes` requires [`quote_id`; `customer_name` or `term_months` or `line_items` or `unit_net_price_annual` or `unit_list_price_annual`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `auto_approve_max_discount_pct` | `number` | `15.0` | Tier 0 maximum net discount percentage allowed without VP approval. |
| `vp_approve_max_discount_pct` | `number` | `25.0` | Tier 1 maximum net discount percentage allowed for Regional Sales VP. |
| `deal_desk_max_discount_pct` | `number` | `35.0` | Tier 2 maximum net discount percentage before CFO/Executive sign-off. |
| `min_gross_margin_floor_pct` | `number` | `60.0` | Minimum blended gross margin % before requiring CFO exception. |

See [`../../README.md`](../../README.md) for the `deal-desk-rfp-engine` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
