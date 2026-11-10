# Test Scenarios: `stakeholder-account-prep`

## Scenario 1 — Mode A: Live CRM + Escalation Stakeholder Brief
- **Prompt:** "Build an executive sponsor prep brief for Meridian BioPharma ahead of Friday's QBR using Salesforce and our escalation tracker."
- **Assertions:**
  - Computes `days_to_renewal`, `days_since_exec_touchpoint`, `health_score`, and `rag_status` via `dossier_synthesizer.py`.
  - Flags `RED` or `AMBER` accounts with overdue milestones and open P1 tickets.

## Scenario 2 — Mode B: Workspace Sheet Fallback with Missing Escalation Feed
- **Prompt:** "CRM connector is down; build the account prep dossier from our Shared Drive Account Health Sheet and flag any missing signal feeds."
- **Assertions:**
  - Emits `UNVERIFIED_INSUFFICIENT_SCOPE` when `missing_feeds` includes escalations.
  - Never assumes `0` open escalations when the feed is missing.

## Scenario 3 — Mode C: Local JSON Account Portfolio Upload
- **Prompt:** "Score `account_signals.json` across Cymbal Financial, Apex Manufacturing, and Northstar Retail and prepare an executive summary."
- **Assertions:**
  - Ranks worst health score / highest ARR at risk first.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.
