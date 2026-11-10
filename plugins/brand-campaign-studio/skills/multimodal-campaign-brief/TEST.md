# Test Scenarios: `multimodal-campaign-brief`

## Scenario 1 — Mode A: Integrated Launch Matrix Audit
- **Prompt:** "Audit Meridian BioPharma Q4 launch plan in Drive for missing Conversion stage assets and budget overrun."
- **Assertions:**
  - Lists missing_funnel_cells and over_budget flag accurately.
  - Assigns LAUNCH_AT_RISK_GAPS_PRESENT.

## Scenario 2 — Mode B: Workspace Schedule Lead-Time Check
- **Prompt:** "Check Drive Launch Tracker Sheet for assets due only 2 days before launch_date."
- **Assertions:**
  - Flags late_assets below 5-day buffer.
  - Includes standard baseline stamp when org_configured is false.

## Scenario 3 — Mode C: Local Brief JSON Matrix Check
- **Prompt:** "Evaluate campaign_brief.json and verify spend variance calculation."
- **Assertions:**
  - Computes exact planned_spend_usd and budget_variance_usd.
  - Maintains HITL approval gate for launch.
