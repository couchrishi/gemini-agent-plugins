# Test Scenarios: `critical-escalation-warroom`

## Scenario 1 — Live Enterprise Connectors: CRM + CSM Sev1 Renewal Clash
- **Prompt:** "Score Stratos Telecom escalation ($650k ARR, renewal in 45 days, 2 Sev1 cases, competitor threat) across CRM and CSM."
- **Assertions:**
  - Assigns exposure_score >= 70 and tier WAR_ROOM_SEV0_EXEC.
  - Lists itemized score drivers.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Escalation Queue Sort
- **Prompt:** "Rank accounts in our Drive VIP Escalation Sheet separating WAR_ROOM from HIGH_TOUCH_TAM."
- **Assertions:**
  - Sorts descending by exposure_score then ARR.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local JSON Escalation Scoring
- **Prompt:** "Run escalation_exposure_scorer.py on escalations.json."
- **Assertions:**
  - Computes arr_at_war_room_risk_usd accurately.
  - Maintains HITL confirmation before alerting.
