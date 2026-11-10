# Test Scenarios: `bom-cost-rollup-variance`

## Scenario 1 — Mode A: SAP Indented BOM Rollup
- **Prompt:** "Roll up 3-level pump assembly BOM standard vs actual PPV with 4% scrap on sub-assemblies."
- **Assertions:**
  - Compounds scrap multipliers cleanly across BOM levels.
  - Ranks top component PPV drivers descending by dollar impact.

## Scenario 2 — Mode B: Workspace Sheet Cyclic BOM Detection
- **Prompt:** "Validate our Drive BOM Workbook containing an accidental sub-assembly circular edge."
- **Assertions:**
  - Captures cycle path in bom_cycles_detected without infinite recursion.
  - Stamps baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local BOM JSON Cost Rollup
- **Prompt:** "Run bom_ppv_rollup.py on bom_costs.json and list PPV alert components (>5%)."
- **Assertions:**
  - Flags alert components >5% PPV and preserves HITL CK24 cost-update gate.
  - Reports extended variance.
