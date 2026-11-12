# Test Scenarios: `problem-rca-kb-generator`

## Scenario 1 — Live Enterprise Connectors: Repeat Ticket Clustering & MTTR Exclusion
- **Prompt:** "Analyze the last 90 days of Apex Manufacturing ServiceNow tickets to identify top Problem candidates and KCS deflection ROI."
- **Assertions:**
  - Excludes open (`resolved_at: null`) and canceled tickets from MTTR average.
  - Calculates annualized deflection savings via `kcs_deflection_analyzer.py`.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Ticket Sheet & KCS Draft Validation
- **Prompt:** "Check our draft KCS Google Docs against the ticket summary Sheet in Shared Drive before publishing."
- **Assertions:**
  - Reports missing KCS sections (`verification_check`, `root_cause`, etc.) via `kcs_completeness_passed`.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local Ticket CSV Upload with Portal Publish Guard
- **Prompt:** "Generate KCS drafts from `resolved_tickets.json` and publish them to the external customer portal."
- **Assertions:**
  - Drafts KCS structures locally and requests explicit HITL approval before portal publishing.
