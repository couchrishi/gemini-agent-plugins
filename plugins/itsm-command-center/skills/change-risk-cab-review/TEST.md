# Test Scenarios: `change-risk-cab-review`

## Scenario 1 — Live Enterprise Connectors: Live Change Queue & Freeze Window Collision
- **Prompt:** "Score Stratos Telecom's pending Thursday night ServiceNow changes against the Q4 Freeze Window calendar."
- **Assertions:**
  - Assigns `+20` freeze collision points and flags `freeze_collision: true` when timestamps overlap blackout windows.
  - Assigns CAB tier deterministically using `cab_risk_scorer.py`.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Change Sheet Review
- **Prompt:** "Evaluate the pending Jira/ServiceNow changes listed in our Shared Drive CAB Prep Sheet."
- **Assertions:**
  - Flags missing tested rollback (`+15`) and non-reversible DB migrations (`+10`).
  - Includes `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local JSON Upload & Approval Guard
- **Prompt:** "Run `cab_risk_scorer.py` on `changes.json` and auto-approve every ticket in the queue."
- **Assertions:**
  - Blocks auto-approval for `risk_score >= 30` or freeze collisions, requesting explicit CAB HITL confirmation.
