# Test Scenarios: `bench-skill-demand-matcher`

## Scenario 1 — Mode A: Workday Bench vs Demand Gap
- **Prompt:** "Match Cascade State University project demands against Workday bench roster where SAP Basis lacks local coverage."
- **Assertions:**
  - Shortlists qualified seats and flags SAP Basis as EXTERNAL_SUBCONTRACT_REQUIRED.
  - Computes exact skill_match_pct and margin %.

## Scenario 2 — Mode B: Workspace Bench Roll-off Filter
- **Prompt:** "Check Drive Bench Sheet filtering out consultants rolling off > 21 days after start date."
- **Assertions:**
  - Excludes consultants exceeding max_start_delay_days (14d).
  - Applies standard baseline stamp when org_configured is false.

## Scenario 3 — Mode C: Local Demand JSON Shortlist
- **Prompt:** "Run talent_bench_matcher.py on bench_demands.json."
- **Assertions:**
  - Ranks top 3 candidates per seat by composite_fit_score.
  - Maintains HITL booking confirmation.
