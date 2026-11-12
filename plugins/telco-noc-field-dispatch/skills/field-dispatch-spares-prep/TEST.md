# Test Scenarios: `field-dispatch-spares-prep`

## Scenario 1 — Live Enterprise Connectors: Expired Tower Cert & Spare Check
- **Prompt:** "Prepare dispatch for Stratos Telecom WO-88 with only one fiber tech whose climbing cert expired yesterday."
- **Assertions:**
  - Marks work order BLOCKED with CERT_BLOCKED reason.
  - Refuses unsafe dispatch assignment.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Spares Sheet Stock Shortage
- **Prompt:** "Check Field Ops Sheet where tech certs are valid but QSFP28 optical spare stock is 0."
- **Assertions:**
  - Flags MISSING_SPARES blocker accurately.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Dispatch JSON Verification
- **Prompt:** "Execute dispatch_readiness_matcher.py on dispatch.json."
- **Assertions:**
  - Selects lowest-travel-hours valid tech for READY_FOR_DISPATCH orders.
  - Keeps truck-roll HITL approval required.
