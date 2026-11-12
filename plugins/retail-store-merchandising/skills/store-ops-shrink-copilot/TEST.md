# Test Scenarios: `store-ops-shrink-copilot`

## Scenario 1 — Live Enterprise Connectors: Store POS Polling vs Phantom Inventory
- **Prompt:** "Analyze Northstar Retail store SKU snapshot where STR-104 has 18 units on hand with 7 zero-scan days and STR-109 has MISSING POS poll."
- **Assertions:**
  - Flags STR-104 SKU as PHANTOM_INVENTORY_ZERO_SCAN and skips STR-109 under unpolled_pos_skipped=1.
  - Ranks tasks by financial impact_score_usd.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Cycle Count Variance Sheet
- **Prompt:** "Audit Store Cycle-Count Sheet in Drive for physical shrink > $250 and negative book counts."
- **Assertions:**
  - Flags NEGATIVE_LEDGER_CORRUPTION and HIGH_DOLLAR_SHRINK separately.
  - Stamps baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Store Inventory JSON Audit
- **Prompt:** "Run store_shrink_task_ranker.py on store_shrink.json."
- **Assertions:**
  - Generates prioritized_store_tasks deterministically.
  - Preserves COGS write-off HITL confirmation gate.
