# Test Scenarios: `supplier-rfx-tariff-modeler`

## Scenario 1 — Live Enterprise Connectors: ERP Bid Tariff Shock Modeling
- **Prompt:** "Model a +25% tariff shock on CN origin quotes vs VN and MX bids for Apex Manufacturing."
- **Assertions:**
  - Shifts rank order accurately once landed duty is added.
  - Computes annual_savings_vs_worst_usd cleanly.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Sheet MOQ & Net-90 Payment Check
- **Prompt:** "Compare supplier quotes in our Drive RFx Sheet including Net 90 vs Net 30 financing value."
- **Assertions:**
  - Adjusts landed cost for working-capital cost of capital and defect PPM.
  - Emits baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local RFx JSON Ranking
- **Prompt:** "Simulate landed_cost_simulator.py on rfx_bids.json with +15% tariff shock."
- **Assertions:**
  - Produces deterministic cost_rank and preserves HITL award gate.
  - Flags infeasible MOQ quotes.
