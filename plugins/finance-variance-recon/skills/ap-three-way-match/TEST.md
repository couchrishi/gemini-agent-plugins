# Test Scenarios: `ap-three-way-match`

## Scenario 1 — Mode A: Multi-Currency SAP Invoices with TCURX Zero-Decimal Scaling & SHKZG Credit
- **Prompt:** "Run AP 3-way match on Apex Manufacturing's JPY and USD invoices from SAP OData."
- **Assertions:**
  - Scales zero-decimal JPY (`sap_raw_encoding: true`) accurately via `reconcile_3way.py` and treats `SHKZG='H'` rows as credits rather than positive duplicates.
  - Flags missing GRNs as `MISSING_GRN` rather than assuming zero variance.

## Scenario 2 — Mode B: Google Sheets Exception Queue with Duplicate & Bank-Change Hold
- **Prompt:** "Audit our Drive AP Exception Sheet where a vendor submitted a same-amount duplicate invoice and a Gmail bank account change."
- **Assertions:**
  - Flags `DUPLICATE_SUSPECT_FUZZY` and `FRAUD_HOLD_BANK_CHANGE`, holding payment automatically.
  - Emits `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Mode C: Separate `--po`, `--gr`, `--invoice` Local Files
- **Prompt:** "Reconcile `po.json`, `gr.json`, and `invoices.json` via CLI and output markdown exceptions."
- **Assertions:**
  - Detects unit price variance exceeding `2%` / `$500` and blocks ERP payment release pending HITL approval.
