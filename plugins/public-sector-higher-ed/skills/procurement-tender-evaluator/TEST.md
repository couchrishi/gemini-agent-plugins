# Test Scenarios: `procurement-tender-evaluator`

## Scenario 1 — Mode A: Debarred Low Bid Price Denominator Guard
- **Prompt:** "Evaluate CivicFirst Agency RFP bids where a $120k vendor is debarred/sanctioned and compliant bids are $200k and $250k."
- **Assertions:**
  - Disqualifies $120k bidder immediately and uses $200k as lowest_compliant_price_usd.
  - Ranks compliant bidders accurately by weighted_total_score.

## Scenario 2 — Mode B: Drive Bid Tabulation COI & Tax Check
- **Prompt:** "Audit Procurement Bid Sheet in Drive where one bidder lacks signed COI attestation."
- **Assertions:**
  - Assigns MISSING_COI_ATTESTATION and DISQUALIFIED_NON_COMPLIANT.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local Tender JSON Evaluation
- **Prompt:** "Execute tender_weighted_scorer.py on tender.json."
- **Assertions:**
  - Outputs deterministic rank and weighted scores cleanly.
  - Preserves Procurement Board HITL award gate.
