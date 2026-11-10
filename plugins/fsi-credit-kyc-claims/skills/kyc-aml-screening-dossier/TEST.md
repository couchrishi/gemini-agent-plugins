# Test Scenarios: `kyc-aml-screening-dossier`

## Scenario 1 — Mode A: Multi-Hop Cayman Holding UBO Drop
- **Prompt:** "Trace Cymbal Financial onboarding entity owned via two 60%/50% indirect holding layers registered in KY."
- **Assertions:**
  - Computes 30% cumulative effective ownership and drops UBO threshold to 10% due to KY EDD.
  - Sets kyc_risk_tier=EDD_MLRO_ESCALATION_REQUIRED.

## Scenario 2 — Mode B: Workspace AML Velocity & Structuring
- **Prompt:** "Audit Drive AML Transaction Sheet with 4.2x 30d volume spike and 6 cash deposits between $9,100-$9,800."
- **Assertions:**
  - Flags both velocity_spike_alert=true and structuring_alert=true.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local Corporate Graph JSON Screen
- **Prompt:** "Execute ubo_velocity_screener.py on kyb_graph.json."
- **Assertions:**
  - Aggregates split paths to the same individual UBO accurately.
  - Preserves MLRO HITL confirmation gate.
