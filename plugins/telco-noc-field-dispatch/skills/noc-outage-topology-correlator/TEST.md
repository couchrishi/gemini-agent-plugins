# Test Scenarios: `noc-outage-topology-correlator`

## Scenario 1 — Mode A: Core Fiber Cut Storm Suppression
- **Prompt:** "Correlate Stratos Telecom alarm flood with 1 metro agg router alarm feeding 18 alarming 5G gNodeBs serving 12,400 subscribers."
- **Assertions:**
  - Collapses 19 raw alarms into 1 P1_CRITICAL root incident with ~94.7% noise reduction.
  - Rolls up impacted_subscribers and enterprise_vip_circuits cleanly.

## Scenario 2 — Mode B: Drive Alarm Sheet Ring Graph
- **Prompt:** "Analyze Drive Topology & Alarm Export Sheet containing redundant ring links."
- **Assertions:**
  - Terminates cleanly without cycle recursion.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local NOC Topology JSON Run
- **Prompt:** "Run alarm_topology_correlator.py on noc_alarms.json."
- **Assertions:**
  - Groups suppressed_child_nodes under each root_node_id.
  - Maintains NOC IC HITL incident gate.
