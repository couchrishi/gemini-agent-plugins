# Test Scenarios: `pnl-budget-variance-bridge`

## Scenario 1 — Live Enterprise Connectors: BigQuery GL Actual vs Budget with Parent Summary Rows
- **Prompt:** "Build the Northstar Retail Q3 P&L constant-currency variance bridge from BigQuery GL actuals containing both parent rollup and leaf rows."
- **Assertions:**
  - Excludes `row_type == "summary"` rows from consolidated totals while asserting tie-out within `$1.00`.
  - Correctly marks revenue upside `FAVORABLE` and OpEx overspend `UNFAVORABLE`.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Sheets Close Workbook with FX Fluctuation
- **Prompt:** "Bridge EMEA software revenue and cloud COGS variance from our Finance Close Sheet using actual vs budget FX rates."
- **Assertions:**
  - Splits total variance into `constant_fx_variance_usd` and `fx_translation_impact_usd` accurately.
  - Emits `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local GL Extract with Hierarchy Tie-Out Break
- **Prompt:** "Run `pnl_variance_engine.py` on `gl_variance.json` containing an out-of-balance summary parent row."
- **Assertions:**
  - Populates `hierarchy_tieout_breaks` when summary vs leaf sum diverges beyond `$1.00`.
  - Ranks material variances `>= $25,000` in `top_material_drivers`.
