# Test Scenarios: `logistics-sla-dispute-resolver`

## Scenario 1 — Live Enterprise Connectors: Merchant Prep vs Courier Transit Fault
- **Prompt:** "Adjudicate Veloce SuperApp order 42 minutes late where merchant kitchen took 45m (15m SLA) and courier took 20m."
- **Assertions:**
  - Assigns attribution=MERCHANT_PREP_BREACH with 100% merchant_liability_usd.
  - Flags high-value refunds for HITL approval.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive SLA Sheet Weather Force Majeure
- **Prompt:** "Evaluate Drive SLA Dispute Sheet with verified storm alert and missing GPS dropoff timestamp."
- **Assertions:**
  - Waives merchant penalty on weather alert and holds null timestamp in MISSING_TELEMETRY_HOLD.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local SLA Disputes JSON Run
- **Prompt:** "Execute zone_sla_dispute_analyzer.py on sla_disputes.json."
- **Assertions:**
  - Rolls up valid_sla_breaches and total_merchant_recovery_usd cleanly.
  - Keeps payouts HITL-gated.
