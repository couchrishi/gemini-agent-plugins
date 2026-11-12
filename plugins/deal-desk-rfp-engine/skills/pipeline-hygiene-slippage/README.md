# Pipeline Hygiene & Slippage Auditor (`pipeline-hygiene-slippage`)

Audits Salesforce CRM opportunity pipelines for stage staleness, close-date slippage pushes, missing MEDDPICC commit gates, single-threading, and multi-currency FX traps. Deterministic computation executes via [`scripts/pipeline_slippage_auditor.py`](scripts/pipeline_slippage_auditor.py). Domain guards enforced: Normalizes multi-currency deals via fx_rates and isolates unmapped currencies; Detects StageName vs is_closed contradictions and SOQL truncation. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **VP of Sales / RevOps Director**: Triggered when running weekly global forecast inspections across USD/EUR/GBP territories; normalizes FX to target currency, isolates closed deals, and exposes single-threaded or repeated-push Commit risk.
- **Regional Sales Manager**: Triggered when auditing late-quarter Commit coverage before board forecast calls; flags stalled stages (`>1.5x` median velocity) and deals with `>=2` close-date pushes.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`pipeline-hygiene-slippage.zip`](../../../../dist/skills/pipeline-hygiene-slippage.zip) (or the full department bundle [`deal-desk-rfp-engine.zip`](../../../../dist/bundles/deal-desk-rfp-engine.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/pipeline-hygiene-slippage` or `@pipeline-hygiene-slippage`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.pipeline_slippage_auditor import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"opportunities": [{"opportunity_id": r.get("Custom opportunity_id"), "stage": r.get("Custom stage")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/deal-desk-rfp-engine/skills/pipeline-hygiene-slippage/scripts/pipeline_slippage_auditor.py \
  --input examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx \
  --config plugins/deal-desk-rfp-engine/skills/pipeline-hygiene-slippage/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `pipeline_slippage_auditor.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail` via `remote_cli mcp`):** "Audit our Q4 Salesforce Commit and BestCase deals across US (USD), EU (EUR), and Japan (JPY) against $4.0M remaining quota."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Review our Revenue Ops Pipeline Sheet in Drive for single-threaded Commit deals and chronic pushers."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx) and ask: "Inspect the attached `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` CRM pipeline tabs in USD, exclude any closed-won/lost noise, compute true Commit coverage, and flag stale, single-threaded, or repeatedly slipped Commit deals."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `4` open opportunities totaling **`$2,477,500.00` USD open (`$1,847,750.00` weighted)** in `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`, pipeline coverage stands at only **`1.03x` (`coverage_target_met: False`)** and **`$1,837,500.00` in Commit deals (`100%` of flagged deals)** shows critical hygiene risk.

- **Slipped Commit Alerts (`OPP-APX-1847` & `OPP-APX-1904`):** `Stratos Bank Core Cloud` (`$480k`, pushed `3x`, `48d` stale) and `Kestrel Logistics Expansion` (`$360k`, pushed `2x`, `39d` stale) both lack an Economic Buyer (`<2` contacts) and next steps.
- **Single-Threaded Renewal & Best Case:** `OPP-APX-1001` (`$997.5k` Commit) and `OPP-APX-1002` (`$640k` Best Case) each carry `0` executive contacts recorded.
- **Approval Confirmation Prompt:** Confirm if you would like to downgrade `OPP-APX-1847` or `OPP-APX-1904` out of Commit via your connected `Salesforce` connector (gated by `Auto-Guardian` on forecast category changes).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx`](../../../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx) (`145.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# CRM Pipeline Hygiene & Slippage Audit (USD)

- **Open Pipeline:** 2,477,500.00 USD (Weighted: 1,847,750.00)
- **Commit at Risk:** 1,837,500.00 USD | **Coverage Ratio:** 1.03x
- **Flagged Opportunities:** 4

| Opportunity | Account | Forecast | Norm Amount | Risk Flags |
| :--- | :--- | :--- | ---: | :--- |
| `OPP-APX-1847` Stratos Bank Core Cloud | Stratos Bank | Commit | 480,000.00 | STALE_STAGE (48d > 21.0d); CHRONIC_SLIPPAGE (pushed 3x); SINGLE_THREADED (0 contacts < 2); MISSING_ECONOMIC_BUYER; MISSING_NEXT_STEP |
| `OPP-APX-1904` Kestrel Logistics Expansion | Kestrel Logistics | Commit | 360,000.00 | STALE_STAGE (39d > 21.0d); CHRONIC_SLIPPAGE (pushed 2x); SINGLE_THREADED (0 contacts < 2); MISSING_ECONOMIC_BUYER; MISSING_NEXT_STEP |
| `OPP-APX-1001` Apex Enterprise Renewal 1 | Partner Tier1 | Commit | 997,500.00 | SINGLE_THREADED (0 contacts < 2) |
| `OPP-APX-1002` Meridian Cloud Platform | Meridian Corp | Best Case | 640,000.00 | SINGLE_THREADED (0 contacts < 2) |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Pipeline Hygiene Audit` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Pipeline Hygiene Audit" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly Salesforce pipeline hygiene and slippage audit using scripts/pipeline_slippage_auditor.py. Normalize multi-currency opportunities, identify stale stages, >=2 push-count deals, single-threaded Commit opportunities, and StageName/IsClosed inconsistencies without modifying CRM records autonomously."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `remaining_quota_usd`, `opportunities`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `opportunities` requires [`opportunity_id` or `name`; `stage` or `forecast_category` or `amount`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `target_currency` | `string` | `USD` | Reporting currency for multi-currency pipeline normalization. |
| `stage_stale_multiplier` | `number` | `1.5` | Multiplier against median stage duration flagging stale deals. |
| `max_push_count_before_flag` | `integer` | `2` | Close-date push count threshold flagging chronic slippage. |
| `min_commit_contacts` | `integer` | `2` | Minimum active contacts required for Commit deals to avoid single-threading. |
| `target_pipeline_coverage_x` | `number` | `3.0` | Target weighted/open pipeline coverage multiple against remaining quota. |

See [`../../README.md`](../../README.md) for the `deal-desk-rfp-engine` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
