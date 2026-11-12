# Test Scenarios: `merchandising-assortment-planner`

## Scenario 1 — Live Enterprise Connectors: Margin-Destructive Promo Detection
- **Prompt:** "Evaluate Northstar Retail 7-day beverage promo with $18k cannibalization loss and $12k media spend against 28-day baseline."
- **Assertions:**
  - Normalizes 28d baseline to 7d run rate and classifies deep-discount net loss as MARGIN_DESTRUCTIVE.
  - Calculates exact promo_roi_ratio.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Promo Sheet Coop & Halo Credits
- **Prompt:** "Check Merchandising Promo Sheet with vendor coop funding and cross-category basket halo."
- **Assertions:**
  - Includes vendor_funding_rebate_usd and halo_gm_gain_usd in net_incremental_gm_usd.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Promo Campaign JSON Run
- **Prompt:** "Execute promo_lift_analyzer.py on promos.json."
- **Assertions:**
  - Ranks campaigns by net_incremental_gm_usd descending.
  - Keeps chain markdown sign-off HITL-gated.
