# Test Scenarios: `sow-scope-margin-auditor`

## Scenario 1 — Live Enterprise Connectors: SharePoint SOW Unbounded Revisions
- **Prompt:** "Audit CivicFirst Agency SOW draft containing 'all work required at no additional cost regardless' and 18% margin."
- **Assertions:**
  - Blocks SOW as BLOCKED_SCORE_9 with itemized clause/margin blockers.
  - Flags missing client dependencies if omitted.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Docs Deliverable Acceptance Gap
- **Prompt:** "Check SOW Doc in Drive with a 20-day acceptance window and 2 deliverables lacking criteria."
- **Assertions:**
  - Flags extended acceptance window and missing_acceptance_criteria_count=2.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local SOW JSON Lint
- **Prompt:** "Run sow_margin_linter.py on sow.json."
- **Assertions:**
  - Separates Score-9 blockers vs Score-3 warnings clearly.
  - Maintains HITL sign-off requirement.
