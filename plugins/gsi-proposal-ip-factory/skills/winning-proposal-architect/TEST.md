# Test Scenarios: `winning-proposal-architect`

## Scenario 1 — Mode A: Onshore-Heavy Pyramid Margin Check
- **Prompt:** "Model Stratos Telecom CRM migration staffing pyramid in Drive with 25% offshore leverage and 26% gross margin."
- **Assertions:**
  - Flags below_offshore_target=true and FINANCE_DESK_EXCEPTION_REQUIRED.
  - Computes exact blended_bill_rate_hourly.

## Scenario 2 — Mode B: Workspace Pricing Sheet < 20% Breach
- **Prompt:** "Check our Drive Pricing Pyramid Sheet where discounts dropped gross margin to 18.5%."
- **Assertions:**
  - Sets margin_gate=CRITICAL_BELOW_20_BLOCKED.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local Staffing JSON Verification
- **Prompt:** "Execute staffing_pyramid_calculator.py on pyramid.json and verify phase math."
- **Assertions:**
  - Reconciles phase revenue/cost sums cleanly.
  - Respects HITL submission gate.
