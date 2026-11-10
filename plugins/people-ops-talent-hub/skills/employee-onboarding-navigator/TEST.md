# Test Scenarios: `employee-onboarding-navigator`

## Scenario 1 — Mode A: HRSD Missing Day-1 SSO Task
- **Prompt:** "Check upcoming Stratos Telecom hires in Workday/ServiceNow HRSD for missing laptop or SSO gates."
- **Assertions:**
  - Flags AT_RISK_MISSING_DAY1_GATES whenever identity_sso_provisioning is omitted.
  - Computes exact overdue_tasks and blocked dependencies.

## Scenario 2 — Mode B: Workspace Onboarding Tracker
- **Prompt:** "Audit our Drive Onboarding Sheet for hires > 30 days past start with incomplete compliance tasks."
- **Assertions:**
  - Calculates days_since_start and overdue task counts accurately.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local New-Hire JSON Plan
- **Prompt:** "Run onboarding_plan_builder.py on hires.json as of 2026-11-10."
- **Assertions:**
  - Breaks down phase completion across day_1/day_30/day_60/day_90.
  - Surfaces stalled hires cleanly.
