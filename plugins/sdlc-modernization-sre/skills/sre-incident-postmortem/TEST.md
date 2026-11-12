# Test Scenarios: `sre-incident-postmortem`

## Scenario 1 — Live Enterprise Connectors: Multi-Incident SLO Error-Budget Calculation
- **Prompt:** "Compute 30-day SLO error-budget burn and TTD/TTM/TTR intervals for Stratos Telecom's core auth incidents."
- **Assertions:**
  - Computes exact `ttd_minutes`, `ttm_minutes`, `ttr_minutes`, and `error_budget_consumed_pct` via `slo_timeline_calculator.py`.
  - Flags `slo_breached: true` when achieved availability falls below `99.9%`.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Postmortem Doc Action SLA Audit
- **Prompt:** "Audit the open corrective actions in our SRE Postmortem Google Doc and flag overdue items."
- **Assertions:**
  - Marks items past `due_date` as `OVERDUE` and null due dates as `MISSING_DUE_DATE`.
  - Includes `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.

## Scenario 3 — Optional Local File Sandbox: Local Timeline JSON Upload
- **Prompt:** "Calculate error budget impact from `postmortem_timeline.json` and format as a Markdown executive brief."
- **Assertions:**
  - Outputs clean Markdown table with exact TTD/TTM/TTR values and zero manual estimation.
