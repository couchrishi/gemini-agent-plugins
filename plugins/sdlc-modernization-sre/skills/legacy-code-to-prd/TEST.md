# Test Scenarios: `legacy-code-to-prd`

## Scenario 1 — Mode A: Monolith Coupling & Hotspot Discovery
- **Prompt:** "Parse Cymbal Financial's legacy settlement service modules in GitHub and extract DB couplings and complexity hotspots."
- **Assertions:**
  - Extracts entrypoints, SQL `db_reads` and `db_writes`, and flags cyclomatic complexity `>= 15` via `spec_traceability_matrix.py`.
  - Computes `traceability_coverage_pct` and lists `untested_critical_requirements`.

## Scenario 2 — Mode B: Workspace Inventory Fallback
- **Prompt:** "Read our Legacy Inventory Sheet in Drive and generate a PRD traceability report."
- **Assertions:**
  - Checks `traceability_gate_passed` against `min_requirement_traceability_pct`.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Mode C: Local JSON Upload with Truncation & Jira Hold
- **Prompt:** "Run `spec_traceability_matrix.py` on `legacy_inventory.json` and create Jira epics for every untested requirement."
- **Assertions:**
  - Emits `TRUNCATION_WARNING` if `metadata.truncated` is `true`.
  - Requests explicit HITL approval before creating any Jira tickets.
