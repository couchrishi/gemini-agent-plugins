# Test Scenarios: `csat-churn-signal-miner`

## Scenario 1 — Mode A: Survey Export with Null Ratings
- **Prompt:** "Analyze Veloce SuperApp CSAT responses where 2 of 6 rows omitted csat_score."
- **Assertions:**
  - Excludes null rows from avg_csat denominator (sets unrated_csat_excluded=2).
  - Captures explicit churn-intent phrases in churn_alerts.

## Scenario 2 — Mode B: Drive Survey Sheet Driver Pareto
- **Prompt:** "Quantify latency vs support responsiveness ARR exposure in Drive CSAT Sheet."
- **Assertions:**
  - Ranks driver_pareto descending by arr_exposed_usd.
  - Emits baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local Verbatim JSON Audit
- **Prompt:** "Run verbatim_driver_quantifier.py on survey_responses.json."
- **Assertions:**
  - Computes exact NPS score and detractor ARR totals.
  - Maintains HITL gate before CRM outreach.
