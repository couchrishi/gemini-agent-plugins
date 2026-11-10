# Test Scenarios: `commercial-credit-memo-analyst`

## Scenario 1 — Mode A: Borrower Stress Covenant Break
- **Prompt:** "Stress-test Cymbal Financial's borrower spread with $12M EBITDA, $42M floating debt, under -20% revenue and +200bps."
- **Assertions:**
  - Calculates exact Base vs Stress DSCR and Net Leverage.
  - Flags CREDIT_COMMITTEE_CONDITIONS when stress case breaches DSCR < 1.10x.

## Scenario 2 — Mode B: Workspace Spread Sheet Audit
- **Prompt:** "Check Borrower Credit Spread Sheet in Drive with 4.5x Net Leverage and 1.05x Base DSCR."
- **Assertions:**
  - Flags base_breach_count=1 and DECLINE_OR_RESTRUCTURE.
  - Includes standard baseline stamp when org_configured is false.

## Scenario 3 — Mode C: Local Credit JSON Evaluation
- **Prompt:** "Run credit_covenant_stress.py on borrowers.json and verify HITL gate."
- **Assertions:**
  - Outputs Base, Mild, and Severe stress tables accurately.
  - Keeps credit commit HITL-gated.
