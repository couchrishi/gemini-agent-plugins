# Test Scenarios: `b2b-order-fallout-resolver`

## Scenario 1 — Live Enterprise Connectors: High-MRC B2B Fallout Backlog
- **Prompt:** "Triage Stratos Telecom B2B fallout queue with aged $4,200/mo DIA circuit hitting OLT port capacity and $1,100/mo SIP LNP freeze."
- **Assertions:**
  - Escalates aged $4,200/mo order as P1_EXEC_ESCALATE under FIBER_FACILITY_CAPACITY_SHORTAGE.
  - Computes annualized_arr_blocked_usd accurately.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Fallout Queue Classification
- **Prompt:** "Classify B2B Fallout Sheet in Drive across credit holds, demarc address failures, and CPE backorders."
- **Assertions:**
  - Assigns deterministic owner queues per bucket.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Fallout JSON Audit
- **Prompt:** "Run order_fallout_classifier.py on fallout.json."
- **Assertions:**
  - Produces sorted bucket_rollup and order priorities.
  - Maintains HITL escalation gate.
