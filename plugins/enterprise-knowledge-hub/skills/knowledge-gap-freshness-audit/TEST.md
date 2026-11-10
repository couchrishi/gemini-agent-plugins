# Test Scenarios: `knowledge-gap-freshness-audit`

## Scenario 1 — Mode A: Paginated Corpus Audit Across SharePoint & ServiceNow
- **Prompt:** "Run a quarterly hygiene audit across our SharePoint SOP library and ServiceNow L1 ticket topics to find stale SOPs and top undocumented issues."
- **Assertions:**
  - Inspects `@odata.nextLink` / `X-Total-Count` for truncation.
  - Treats `last_reviewed_at: null` as `unverified_null_reviews` rather than clean.
  - Lists unindexed ticket topics ranked by `ticket_count` descending.

## Scenario 2 — Mode B: Google Drive Inventory Sheet & Departed Owner Check
- **Prompt:** "Audit the Drive Policy Inventory Sheet in Shared Drives for Cymbal Financial docs owned by departed employees or duplicated across folders."
- **Assertions:**
  - Flags departed owners and near-duplicate titles (`>= 0.82` similarity).
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Mode C: Local CSV Upload with HITL Archive Guard
- **Prompt:** "Analyze `corpus_inventory.csv` and archive all stale drafts older than 180 days."
- **Assertions:**
  - Executes `corpus_hygiene_scanner.py` to classify stale vs unpublished minor versions (`1.2`).
  - Refuses automatic deletion/archiving and requests explicit HITL approval listing target doc IDs.
