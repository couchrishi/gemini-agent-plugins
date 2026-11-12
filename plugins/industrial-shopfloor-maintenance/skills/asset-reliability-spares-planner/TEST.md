# Test Scenarios: `asset-reliability-spares-planner`

## Scenario 1 — Live Enterprise Connectors: SAP PM Critical Pump Seal Stockout
- **Prompt:** "Check Apex Manufacturing compressor mechanical seals with 0 on-hand and 21-day lead time."
- **Assertions:**
  - Flags CRITICAL_STOCKOUT_EXPEDITE and computes exact ROP and order qty.
  - Computes lead_time_demand_units cleanly.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Sheet Censored Zero-Failure Part
- **Prompt:** "Evaluate Drive Spares Sheet including an ultra-critical turbine bearing with 0 failures in 12,000h."
- **Assertions:**
  - Sets zero_failure_censored=true with finite conservative MTBF.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Spares JSON Optimization
- **Prompt:** "Run mtbf_spares_optimizer.py on spares.json."
- **Assertions:**
  - Computes total_recommended_spend_usd accurately.
  - Maintains HITL requisition gate.
