# Test Scenarios: `pharmacovigilance-safety-intake`

## Scenario 1 — Mode A: 7-Day Fatal Unexpected SUSAR Watch
- **Prompt:** "Screen Meridian BioPharma safety cases including a fatal unexpected SUSAR aware on 2026-11-05 as of 2026-11-10."
- **Assertions:**
  - Assigns 7-Day Fatal/LT SUSAR clock (due 2026-11-12, 2 days left -> EXPEDITED_SIGN_OFF_URGENT).
  - Validates all 4 ICH criteria.

## Scenario 2 — Mode B: Safety Log Unredacted PHI Detection
- **Prompt:** "Audit Drive Safety Intake Sheet where a reporter pasted an SSN (123-45-6789) and email in the narrative."
- **Assertions:**
  - Flags phi_detected=['SSN', 'Email'] and intake_status=PHI_REDACTION_REQUIRED.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local ICSR Missing Suspect Drug
- **Prompt:** "Run icsr_completeness_checker.py on safety_cases.json containing a case missing suspect_drug."
- **Assertions:**
  - Marks valid_4_ich_criteria=false and INCOMPLETE_FOLLOWUP_REQUIRED.
  - Preserves QPPV HITL submission gate.
