# Test Scenarios: `structured-hiring-rubric`

## Scenario 1 — Live Enterprise Connectors: Greenhouse Split Scorecards
- **Prompt:** "Calibrate Greenhouse scorecards for Cymbal Financial Staff Engineer candidate with scores [4, 1, 4, 3]."
- **Assertions:**
  - Flags score_spread=3.0 (>=2.0) and strong_no_hire_veto=true.
  - Assigns calibration_status=DEBRIEF_REQUIRED_SPLIT_PANEL.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Docs Thin & Biased Notes
- **Prompt:** "Audit the Debrief Doc in Drive containing 'good culture fit, high energy for recent grad' in 25 chars."
- **Assertions:**
  - Flags both bias_flags and thin_evidence_flags -> CALIBRATION_BLOCKED_BIAS_OR_THIN_EVIDENCE.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Scorecard JSON Clean Consensus
- **Prompt:** "Evaluate scorecards.json for consensus candidates and verify HITL offer gate."
- **Assertions:**
  - Computes exact mean_score and sets HIRE_RECOMMENDED_FOR_HITL without auto-extending offers.
  - Preserves strict evidence completeness.
