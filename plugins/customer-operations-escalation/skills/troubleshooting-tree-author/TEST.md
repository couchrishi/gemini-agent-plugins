# Test Scenarios: `troubleshooting-tree-author`

## Scenario 1 — Live Enterprise Connectors: Graph Integrity Audit with Cycle & Dead End
- **Prompt:** "Validate our payment-timeout diagnostic tree JSON containing an infinite retry loop and a dangling branch target."
- **Assertions:**
  - Captures exact cycle path and broken reference, setting graph_valid=false.
  - Lists unreachable orphan nodes separately.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Playbook Tree Depth Check
- **Prompt:** "Audit Support Playbook tree from Drive with 8 nested diagnostic hops."
- **Assertions:**
  - Flags exceeds_max_hops=true when depth > 6.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Clean Decision Tree Pass
- **Prompt:** "Run decision_tree_validator.py on clean_tree.json before Knowledge Lead publish."
- **Assertions:**
  - Reports graph_valid=true with 0 defects.
  - Requires HITL sign-off to publish.
