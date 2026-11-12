# Test Scenarios: `executive-data-story-pack`

## Scenario 1 — Live Enterprise Connectors: BigQuery Export Profiling & A2UI Payload
- **Prompt:** "Profile our Q4 regional orders export from BigQuery and generate a Canvas chart summarizing revenue by region."
- **Assertions:**
  - Computes quantiles (`p25`, `median`, `p75`, `p95`), IQR outlier counts, and `a2ui_chart_payload` via `dataset_profiler_guard.py`.
  - Emits `TRUNCATION_WARNING` if `row_limit_ceiling` is reached.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Sheets Formula Error Audit
- **Prompt:** "Profile our Northstar Retail Store Scorecard Google Sheet export containing `#REF!` and empty cells."
- **Assertions:**
  - Counts `formula_error_cells` and flags columns with `null_rate_pct > 15%`.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local CSV Upload without Context Flooding
- **Prompt:** "Analyze `dataset.csv` in Python RAM and prepare an executive summary without printing raw rows."
- **Assertions:**
  - Profiles dataset completely in Python RAM and renders compact Markdown summary + chart payload.
