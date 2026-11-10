# Test Scenarios: `insurance-claims-triage-pack`

## Scenario 1 — Mode A: High-Value Cyber Claim Sublimit Cap
- **Prompt:** "Evaluate $350k ransomware claim with $25k deductible, $150k cyber sublimit, and 80% coinsurance."
- **Assertions:**
  - Caps payout at $150k sublimit cleanly and sets reserve_escalation=true (>= $100k).
  - Routes to RESERVE_ESCALATION_SENIOR_ADJUSTER.

## Scenario 2 — Mode B: Drive Claims Sheet Out-of-Period & Exclusion
- **Prompt:** "Check Drive Claims Sheet where CLM-2 occurred after policy expiration and CLM-3 claims excluded flood damage."
- **Assertions:**
  - Denies both with COVERAGE_DENIED_OUT_OF_PERIOD and COVERAGE_DENIED_EXCLUSION ($0 payable).
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local FNOL Claims JSON Batch
- **Prompt:** "Run coverage_limit_evaluator.py on claims.json."
- **Assertions:**
  - Computes exact total_net_payable_usd and flags missing documentation holds.
  - Maintains Adjuster HITL settlement gate.
