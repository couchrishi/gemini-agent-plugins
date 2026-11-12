# Executive Data Story Pack (`executive-data-story-pack`)

Profiles tabular CSV and JSON datasets in RAM for completeness, null rates, formula errors, IQR outliers, quantiles, and truncation ceilings, emitting verified A2UI Canvas chart payloads. Deterministic computation executes via [`scripts/dataset_profiler_guard.py`](scripts/dataset_profiler_guard.py). Domain guards enforced: Detects row_limit_ceiling truncation and spreadsheet #REF!/#N/A errors; Profiles dataset in RAM and outputs verified A2UI chart payload. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **BI Storytelling / Strategy Lead**: Triggered when packaging multi-tab analytical exports into board-ready narrative briefs; profiles column nulls (`>=15%` warn), detects skewed distributions, and checks denominator sample sizes (`n >= 30`).
- **Chief Data Officer Team**: Triggered when reviewing automated data briefs prior to leadership distribution; attaches deterministic data-quality caveats so small-sample fluctuations are never overstated.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`executive-data-story-pack.zip`](../../../../dist/skills/executive-data-story-pack.zip) (or the full department bundle [`conversational-bi-analyst.zip`](../../../../dist/bundles/conversational-bi-analyst.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides` + Customer BYO-MCP (`Semantic BI Layer / Looker MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/executive-data-story-pack` or `@executive-data-story-pack`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.dataset_profiler_guard import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"rows": wb["Source_Tab"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/conversational-bi-analyst/skills/executive-data-story-pack/scripts/dataset_profiler_guard.py \
  --input examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx \
  --config plugins/conversational-bi-analyst/skills/executive-data-story-pack/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `dataset_profiler_guard.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides` + Customer BYO-MCP (`Semantic BI Layer / Looker MCP server`) via `remote_cli mcp`):** "Profile our Q4 regional orders export from BigQuery and generate a Canvas chart summarizing revenue by region."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Profile our Northstar Retail Store Scorecard Google Sheet export containing `#REF!` and empty cells."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx) and ask: "Profile the analytical dataset tabs in `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` for missing-value thresholds, outliers, and spreadsheet formula errors, and synthesize an executive readiness summary without flooding chat with raw table rows."

## Sample Response

### What You See in Gemini Enterprise Chat

Profiling *Apex Global Q3 ARPU Mix Paradox & Funnel Audit* (`5` rows, `7` columns, `truncated: False`, `0` formula errors) in `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` flagged **`1` high-null column (`revenue` at `20.0%` missing)** alongside clean distributions across LTV (median `$3,400.0`) and CAC (median `$410.0`).

- **Completeness Alert (`1` Column):** `revenue` has `20.0%` missing values (`>= 15%` threshold), requiring caveat tagging before publishing headline ARPU slides.
- **Outliers & Margin Signals:** `margin` (`mean $1,070.24`, `2` outliers) and `cac_usd` (`mean $402.0`, `1` outlier) were profiled safely in RAM without formula `#REF!`/`#VALUE!` defects.
- **Approval Confirmation Prompt:** Confirm if you would like to distribute the caveated executive summary deck via your connected `Google Slides`, `Gmail`, or `Outlook` connector.

### Verified Deterministic Engine Output

Executed directly against [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx`](../../../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx) (`146.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Executive Data Story Profile: Apex Global Q3 ARPU Mix Paradox & Funnel Audit

- **Rows:** 5 | **Columns:** 7 | **Truncated:** `False`
- **High-Null Columns:** 1 | **Formula Error Cells:** 0

| Column | Type | Null % | Distinct | Mean / Median | P95 | Outliers |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| `record_id` | numeric | 0.0% | 5 | 0.0 / 0.0 | 0.0 | 0 |
| `region` | numeric | 0.0% | 4 | 0.0 / 0.0 | 0.0 | 0 |
| `segment` | numeric | 0.0% | 3 | 0.0 / 0.0 | 0.0 | 0 |
| `revenue` | numeric | 20.0% | 4 | 1707.5 / 1730.0 | 2355.5 | 0 |
| `margin` | numeric | 0.0% | 5 | 1070.24 / 1049.6 | 1487.36 | 2 |
| `cac_usd` | numeric | 0.0% | 5 | 402.0 / 410.0 | 444.0 | 1 |
| `ltv_usd` | numeric | 0.0% | 5 | 3420.0 / 3400.0 | 4060.0 | 0 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Daily KPI Anomaly Digest` routine via `schedule_task`:

```text
Schedule recurring job "Daily KPI Anomaly Digest" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Run the daily KPI variance and z-score anomaly check using scripts/mix_rate_volume_bridge.py. Decompose revenue/margin changes into exact Volume, Mix, and Rate effects, flag segments exceeding zscore_anomaly_threshold, and save an internal Canvas digest without emailing distribution lists."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `title`, `rows`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `rows` accepts any non-empty row list or table without fixed column requirements.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_null_rate_warn_pct` | `number` | `15.0` | Column null percentage triggering data-quality warning in dataset profiler. |

See [`../../README.md`](../../README.md) for the `conversational-bi-analyst` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
