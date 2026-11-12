# Test Scenarios: `regulatory-change-mapper`

## Scenario 1 — Live Enterprise Connectors: ServiceNow GRC Mapping Against New Regulatory Articles
- **Prompt:** "Map EU DORA operational resilience articles against our ServiceNow GRC control register for Cymbal Financial."
- **Assertions:**
  - Maps `articles` to `controls` via `control_gap_mapper.py`, highlighting `UNCOVERED_GAP` mandates and missing domains.
  - Ranks gaps by severity-weighted `remediation_priority_score`.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Sheets Control Register with Null Audit Dates
- **Prompt:** "Evaluate our Drive Compliance Control Register Sheet where `CTRL-204` has a blank `last_tested_date` and `CTRL-205` is 490 days old."
- **Assertions:**
  - Classifies null `last_tested_date` as `UNVERIFIED_MISSING_EVIDENCE` (never compliant) and `> 365 days` as `STALE_EVIDENCE`.
  - Includes `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local Regulatory Control Matrix Remediation Queue
- **Prompt:** "Analyze `regulatory_controls.json` and prioritize remediation tasks without auto-modifying GRC records."
- **Assertions:**
  - Outputs sorted `remediation_queue` and `overall_compliance_pct`.
  - Enforces HITL gate before updating ServiceNow GRC attestation states.
