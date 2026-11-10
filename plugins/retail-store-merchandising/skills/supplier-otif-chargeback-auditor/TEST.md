# Test Scenarios: `supplier-otif-chargeback-auditor`

## Scenario 1 — Mode A: Late Arrival Chargeback vs Detention
- **Prompt:** "Audit Northstar Retail PO arriving 95 minutes late with 180 minutes dock dwell and 90% fill rate."
- **Assertions:**
  - Flags on_time=false, in_full=false, computes late + short-ship chargebacks, and keeps detention_fee_usd=0.0.
  - Computes net_vendor_recovery_usd cleanly.

## Scenario 2 — Mode B: Drive Receiving Sheet Weather Exclusion
- **Prompt:** "Evaluate DC Receiving Sheet with WEATHER_FORCE_MAJEURE exclusion and on-time carrier detained 4 hours."
- **Assertions:**
  - Waives late chargeback on weather PO and calculates detention_fee_usd for on-time delayed carrier.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local Dock Deliveries JSON Audit
- **Prompt:** "Run otif_detention_calculator.py on otif.json."
- **Assertions:**
  - Outputs vendor_scorecards and meets_sla flags deterministically.
  - Preserves debit-memo HITL confirmation gate.
