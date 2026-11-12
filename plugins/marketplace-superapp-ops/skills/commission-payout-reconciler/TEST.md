# Test Scenarios: `commission-payout-reconciler`

## Scenario 1 — Live Enterprise Connectors: Cross-Currency Variance & Negative Clawback
- **Prompt:** "Reconcile Veloce SuperApp payouts where Merchant A has high refunds causing -$420 balance and Merchant B has $180 FX wire mismatch."
- **Assertions:**
  - Flags Merchant A as NEGATIVE_CLAWBACK_RISK and Merchant B as SETTLEMENT_VARIANCE_EXCEPTION.
  - Computes net_settlement_variance accurately.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Merchant Payout Recon Sheet
- **Prompt:** "Audit Weekly Merchant Payout Sheet in Drive for commission/promo split discrepancies."
- **Assertions:**
  - Separates platform-funded promo credits from merchant-funded promo deductions.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Payout JSON Audit
- **Prompt:** "Run payout_ledger_reconciler.py on payouts.json."
- **Assertions:**
  - Verifies reconciliations deterministically with hitl_hold_required on exceptions.
  - Maintains Finance HITL payout gate.
