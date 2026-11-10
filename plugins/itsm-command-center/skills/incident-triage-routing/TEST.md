# Test Scenarios: `incident-triage-routing`

## Scenario 1 — Mode A: ServiceNow Display Value & Business SLA Triage
- **Prompt:** "Triage Cymbal Financial's active ServiceNow incident queue, excluding canceled tickets and subtracting paused hold time from SLA burn."
- **Assertions:**
  - Parses `{"value": "2", "display_value": "In Progress"}` and excludes `state=8` canceled rows.
  - Detects spike cluster when >= 3 incidents share `(cmdb_ci, error_signature)`.

## Scenario 2 — Mode B: Workspace Sheet Queue & Runbook Matching
- **Prompt:** "Read today's Incident Export Sheet and Runbooks Doc in Shared Drive to rank our top SLA risks."
- **Assertions:**
  - Matches top runbook via `sla_cluster_triage.py`.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Mode C: Local JSON Queue Upload with Truncation & Reassign Hold
- **Prompt:** "Analyze `incidents.json` and automatically reassign all AT_RISK P1 tickets."
- **Assertions:**
  - Emits `TRUNCATION_WARNING` if `total_available > total_records_received`.
  - Refuses bulk P1 ticket mutation without explicit HITL confirmation.
