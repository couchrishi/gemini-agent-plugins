# Test Scenarios: `executed-obligation-extractor`

## Scenario 1 — Live Enterprise Connectors: Live Executed CLM Contracts Expiring Within 30 Days
- **Prompt:** "Audit all Apex Manufacturing executed supplier MSAs in SharePoint for upcoming opt-out deadlines."
- **Assertions:**
  - Calculates `opt_out_deadline = renewal_date - notice_days` exactly via `obligation_calendar_builder.py`.
  - Escalates contracts inside `<= 30 days` (`CRITICAL_URGENT`) and uncapped CPI escalators.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Google Sheets Registry with Missing Notice Window
- **Prompt:** "Scan our Executed Contract Registry Sheet in Drive where two auto-renewing agreements have blank `notice_days`."
- **Assertions:**
  - Marks blank `notice_days` auto-renewal rows as `UNVERIFIED_MISSING_FIELDS` (`urgency: UNVERIFIED`).
  - Emits `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local Executed Contract CSV Calendar Build
- **Prompt:** "Build a sorted obligation calendar from `executed_contracts.csv` as of `2026-11-10`."
- **Assertions:**
  - Produces chronologically ordered `obligation_calendar` entries with exposure amounts.
  - Keeps vendor non-renewal notifications in draft pending explicit user HITL confirmation.
