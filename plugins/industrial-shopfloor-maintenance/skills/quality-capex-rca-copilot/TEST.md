# Test Scenarios: `quality-capex-rca-copilot`

## Scenario 1 — Mode A: QMS Defect Pareto & Lot Quarantine
- **Prompt:** "Analyze Apex Manufacturing CNC plant scrap events across supplier lots and shifts."
- **Assertions:**
  - Identifies top 80% scrap drivers and flags lot >= 2x plant average.
  - Ranks anomalous_supplier_lots by ratio_to_avg.

## Scenario 2 — Mode B: Workspace Sheet CapEx Hurdle Check
- **Prompt:** "Evaluate Drive Quality Sheet proposing a $180k vision inspection cell saving $120k/yr vs $300k saving $60k/yr."
- **Assertions:**
  - Marks 1.50yr proposal meets_payback_hurdle=true and 5.00yr false.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local Scrap JSON Audit
- **Prompt:** "Run defect_pareto_correlator.py on quality_events.json."
- **Assertions:**
  - Reconciles sum of defect scrap_cost_usd to total cleanly.
  - Preserves HITL CapEx approval gate.
