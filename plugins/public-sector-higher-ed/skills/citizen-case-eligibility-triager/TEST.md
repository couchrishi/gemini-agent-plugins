# Test Scenarios: `citizen-case-eligibility-triager`

## Scenario 1 — Live Enterprise Connectors: Due-Process Cure Notice on Missing Income Doc
- **Prompt:** "Triage CivicFirst Agency household-of-4 packet missing proof_of_income with an SSN in free-text notes."
- **Assertions:**
  - Outputs PENDING_VERIFICATION_CURE_NOTICE (not denial) and detects pii_tokens_redacted=1.
  - Calculates 200% FPL household threshold accurately.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Benefits Triage Sheet Verification
- **Prompt:** "Audit Intake Case Sheet in Drive with eligible household under 200% FPL and over-income case."
- **Assertions:**
  - Separates ELIGIBLE_RECOMMEND_AWARD from RECOMMEND_DENIAL_OVER_INCOME cleanly.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Citizen Case Packet JSON Run
- **Prompt:** "Run statutory_eligibility_engine.py on cases.json."
- **Assertions:**
  - All determinations enforce hitl_caseworker_signoff_required=true.
  - Preserves caseworker HITL confirmation gate.
