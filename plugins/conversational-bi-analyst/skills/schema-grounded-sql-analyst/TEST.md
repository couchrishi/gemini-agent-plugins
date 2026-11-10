# Test Scenarios: `schema-grounded-sql-analyst`

## Scenario 1 — Mode A: Missing Partition Filter & Join Fanout Catch
- **Prompt:** "Check this BigQuery SQL joining `purchase_orders` to `goods_receipts` on `po_id` alone without filtering `posting_date`."
- **Assertions:**
  - Flags missing partition filter on `posting_date`.
  - Flags M:N `JOIN_FANOUT_RISK` because `po_item` primary key is missing from `ON` condition and `SUM()` is present.

## Scenario 2 — Mode B: Connected Sheets Query Cost Check
- **Prompt:** "Review Northstar Retail's Connected Sheets BigQuery query estimated at 950 GB scan."
- **Assertions:**
  - Sets `scan_over_budget: true` (`950 > 500`) and requests explicit HITL approval before running.
  - Includes `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Mode C: Uploaded SQL with Destructive DDL
- **Prompt:** "Validate `migration_check.sql` containing a `TRUNCATE TABLE` statement before running against staging."
- **Assertions:**
  - Sets `is_read_only_safe: false`, detects `TRUNCATE`, and blocks execution pending explicit HITL approval.
