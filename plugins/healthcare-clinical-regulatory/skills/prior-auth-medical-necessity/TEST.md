# Test Scenarios: `prior-auth-medical-necessity`

## Scenario 1 — Mode A: FHIR Prior Auth Step-Therapy Gap
- **Prompt:** "Evaluate prior auth PA-401 for biologic therapy requiring two >=30-day step failures when patient completed only one 14-day trial."
- **Assertions:**
  - Flags step therapy shortfall deterministically and assigns MEDICAL_DIRECTOR_REVIEW.
  - Lists met vs unmet criteria clearly.

## Scenario 2 — Mode B: Workspace Checklist Missing Required Labs
- **Prompt:** "Audit Drive Prior Auth packet PA-402 missing required MRI report documentation."
- **Assertions:**
  - Flags missing_labs and assigns PEER_REVIEW_MISSING_DOCS.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local De-Identified Prior Auth Check
- **Prompt:** "Run medical_criteria_matcher.py on prior_auth.json."
- **Assertions:**
  - Sets criteria_met=true for fully compliant packets while keeping physician HITL approval.
  - Handles unmapped CPT codes safely.
