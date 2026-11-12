# Test Scenarios: `ar-aging-collections-audit`

## Scenario 1 — Live Enterprise Connectors: ERP Open AR Subledger with Unapplied Credit Memos
- **Prompt:** "Audit Veloce SuperApp's open AR subledger where a major customer has a $45k `90+` invoice alongside a `-40k` credit memo."
- **Assertions:**
  - Isolates `-$40,000` into `unapplied_credits_usd` while reporting `$45,000` in the `90+` aging bucket via `aging_bucket_auditor.py`.
  - Places customer in `collections_escalation_queue` (`CREDIT_RECON_THEN_DUNNING`).

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Sheets AR Export DSO & Bucket Verification
- **Prompt:** "Compute DSO and bucket totals from our Drive AR Aging Sheet using trailing 90-day credit sales."
- **Assertions:**
  - Computes DSO against consistent gross positive AR and outputs all 5 aging buckets.
  - Emits `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local AR Open Items Dunning Queue Check
- **Prompt:** "Run `aging_bucket_auditor.py` on `ar_open_items.json` and draft dunning escalation packets."
- **Assertions:**
  - Escalates single accounts with `90+ >= $10,000` (`collections_escalation_count`).
  - Refuses autonomous external dunning email transmission without HITL confirmation.
