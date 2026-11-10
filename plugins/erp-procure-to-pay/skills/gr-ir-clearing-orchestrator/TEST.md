# Test Scenarios: `gr-ir-clearing-orchestrator`

## Scenario 1 — Mode A: SAP EKBE JPY & SHKZG Reconciliation
- **Prompt:** "Reconcile Apex Manufacturing SAP EKBE GR/IR lines including JPY raw postings and SHKZG='H' reversals."
- **Assertions:**
  - Normalizes JPY scaling and cancels SHKZG reversals accurately.
  - Separates GR_WITHOUT_IR vs IR_WITHOUT_GR.

## Scenario 2 — Mode B: Workspace GR/IR Aging Audit
- **Prompt:** "Check our Drive GR/IR Aging Sheet as of 2026-11-10 for accruals open > 60 days."
- **Assertions:**
  - Flags aging_breach=true on lines > 60 days old.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local GR/IR Postings JSON Check
- **Prompt:** "Run gr_ir_reconciler.py on grir_postings.json and verify MR11 safety."
- **Assertions:**
  - Marks balanced lines BALANCED_CLEARED and keeps SAP postings HITL-gated.
  - Computes total_abs_imbalance_usd cleanly.
