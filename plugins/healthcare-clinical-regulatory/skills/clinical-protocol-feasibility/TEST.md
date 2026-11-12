# Test Scenarios: `clinical-protocol-feasibility`

## Scenario 1 — Live Enterprise Connectors: CTMS Protocol SoA Primary Endpoint Conflict
- **Prompt:** "Audit Meridian BioPharma Phase III protocol where Day-180 Visit omits the biopsy required for the Primary Endpoint."
- **Assertions:**
  - Flags MISSING_ENDPOINT_ASSESSMENT and assigns PROTOCOL_AMENDMENT_REQUIRED_PRIMARY_GAP.
  - Identifies missing procedure explicitly.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Feasibility Sheet Accrual Shortfall
- **Prompt:** "Evaluate Drive Site Feasibility Sheet with 40% screen failure rates and 2 sites awaiting IRB approval."
- **Assertions:**
  - Discounts enrollment by screen failure and unapproved IRB status, reporting enrollment_shortfall.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Protocol JSON Check
- **Prompt:** "Run soa_endpoint_validator.py on protocol.json."
- **Assertions:**
  - Verifies 100% endpoint assessment coverage cleanly.
  - Maintains HITL clinical sign-off gate.
