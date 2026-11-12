# KPI Anomaly & Driver Tree (`kpi-anomaly-driver-tree`)

Computes zero-residual Volume-Mix-Rate KPI bridges and z-score segment anomalies across period-over-period tables in RAM. Deterministic computation executes via [`scripts/mix_rate_volume_bridge.py`](scripts/mix_rate_volume_bridge.py). Domain guards enforced: Volume + Mix + Rate effects sum strictly to total_delta with zero residual; Flags segments below min_sample_size_guard with low_sample_caution. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **FP&A / Revenue Analytics Lead**: Triggered when explaining counter-intuitive executive KPI moves such as blended ARPU jumps; computes exact zero-residual Volume, Mix, and Rate effects to expose Simpson's paradox across segments.
- **Growth & Monetization PM**: Triggered when detecting regional conversion or unit-economics shifts across enterprise vs SMB cohorts; flags statistically significant `|z| >= 2.0` segment swings separated from mix shifts.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`kpi-anomaly-driver-tree.zip`](../../../../dist/skills/kpi-anomaly-driver-tree.zip) (or the full department bundle [`conversational-bi-analyst.zip`](../../../../dist/bundles/conversational-bi-analyst.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides` + Customer BYO-MCP (`Semantic BI Layer / Looker MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/kpi-anomaly-driver-tree` or `@kpi-anomaly-driver-tree`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.mix_rate_volume_bridge import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"segments": [{"segment": r.get("Custom segment"), "current_revenue": r.get("Custom current_revenue")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/conversational-bi-analyst/skills/kpi-anomaly-driver-tree/scripts/mix_rate_volume_bridge.py \
  --input examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx \
  --config plugins/conversational-bi-analyst/skills/kpi-anomaly-driver-tree/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `mix_rate_volume_bridge.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides` + Customer BYO-MCP (`Semantic BI Layer / Looker MCP server`) via `remote_cli mcp`):** "Explain Veloce SuperApp's Q3-to-Q4 net revenue change across Ride, Food, and Mart segments from BigQuery."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check our Revenue KPI Sheet in Shared Drive for statistically anomalous drops (`|z| >= 2.0`) and small-sample alerts."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx) and ask: "Using the segment revenue and volume data in `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`, build a zero-residual Volume-Mix-Rate bridge from prior to current period and separate true segment rate shifts from Simpson's paradox mix effects."

## Sample Response

### What You See in Gemini Enterprise Chat

Decomposing the **`+$876,000.00` total revenue increase** (`$1,360,000.00 -> $2,236,000.00`) across `3` segments in `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` proves that **`+$888,888.89` (`101.5%` of total growth) came from favorable Mix Shift toward `Enterprise-NorthAM`**, masking an underlying **`-$164,000.00` Rate erosion** (`-0.0` bridge residual).

- **Zero-Residual Bridge:** Volume effect `+$151,111.11` + Mix effect `+$888,888.89` + Rate effect `-$164,000.00` reconciles exactly to `+$876,000.00` (`0` statistical `|z| >= 2.0` single-segment anomalies).
- **Segment Divergence:** `Enterprise-NorthAM` surged `+$1,404,000.00` (`-$96,000` rate compression), offsetting contractions in `Enterprise-APAC` (`-$280,000`) and `SelfServe-SMB` (`-$248,000`).
- **Approval Confirmation Prompt:** Confirm if you would like to share this Volume-Mix-Rate executive driver pack with leadership via your connected `Google Slides`, `Gmail`, or `Outlook` connector.

### Verified Deterministic Engine Output

Executed directly against [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx) (`178.2 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Volume-Mix-Rate KPI Bridge & Anomaly Tree

- **Prior -> Current:** 1,360,000.00 -> 2,236,000.00 (**Delta:** +876,000.00)
- **Bridge Decomposition:** Volume `+151,111.11` | Mix `+888,888.89` | Rate `-164,000.00` (Residual: `-0.0`)
- **Z-Score Anomalies:** 0

| Segment | Prior | Current | Delta | Volume | Mix | Rate | Z-Score | Anomaly |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| Enterprise-NorthAM | 300,000.00 | 1,704,000.00 | +1,404,000.00 | +755,555.56 | +727,901.23 | -96,000.00 | +1.41 | `False` |
| Enterprise-APAC | 660,000.00 | 380,000.00 | -280,000.00 | -151,111.11 | -91,851.85 | -60,000.00 | -0.67 | `False` |
| SelfServe-SMB | 400,000.00 | 152,000.00 | -248,000.00 | -453,333.33 | +252,839.51 | -8,000.00 | -0.75 | `False` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily KPI Anomaly Digest` routine via `schedule_task`:

```text
Schedule recurring job "Daily KPI Anomaly Digest" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Run the daily KPI variance and z-score anomaly check using scripts/mix_rate_volume_bridge.py. Decompose revenue/margin changes into exact Volume, Mix, and Rate effects, flag segments exceeding zscore_anomaly_threshold, and save an internal Canvas digest without emailing distribution lists."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `segments`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `segments` requires [`segment`; `current_revenue` or `prior_revenue` or `current_volume`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `default_currency` | `string` | `USD` | Default analytical reporting currency. |
| `zscore_anomaly_threshold` | `number` | `2.0` | Absolute z-score threshold flagging KPI segment anomalies. |
| `materiality_amount_threshold` | `number` | `25000.0` | Absolute variance materiality threshold in reporting currency. |
| `min_sample_size_guard` | `integer` | `30` | Minimum denominator sample size before emitting LOW_SAMPLE_SIZE caution. |

See [`../../README.md`](../../README.md) for the `conversational-bi-analyst` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
