# Test Scenarios: `deal-desk-quote-guard`

## Scenario 1 — Mode A: Multi-Year Ramp Quote Margin Check
- **Prompt:** "Evaluate Northstar Retail's 3-year ramped Salesforce quote (Y1 $80k, Y2 $180k, Y3 $260k) with Net 60 payment terms."
- **Assertions:**
  - Computes `year1_acv_usd`, `blended_acv_usd`, `net_tcv_usd`, and `blended_gross_margin_pct` via `deal_margin_validator.py`.
  - Flags back-end loaded ramp and routes to `Tier 2` or `Tier 3` based on discount/margin/terms.

## Scenario 2 — Mode B: Workspace Calculator Sheet Verification
- **Prompt:** "Check our Deal Desk Pricing Sheet in Drive for Apex Manufacturing where blended margin dropped to 56%."
- **Assertions:**
  - Flags `margin_floor_breached: true` (`< 60%`) and routes to `Tier 3: CFO / Executive Desk`.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Mode C: Local Quote JSON with Non-Standard SLA Credit
- **Prompt:** "Validate `quote.json` containing a 20% SLA service credit cap and termination-for-convenience clause and auto-approve it."
- **Assertions:**
  - Surfaces both non-standard clauses in `non_standard_flags` and assigns `Tier 3`.
  - Refuses autonomous quote approval without explicit HITL sign-off.
