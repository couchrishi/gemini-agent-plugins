# Test Scenarios: `ehs-safety-permit-auditor`

## Scenario 1 — Mode A: Confined-Space Stale Gas & Missing LOTO
- **Prompt:** "Audit Apex Manufacturing confined-space vessel permit PTW-101 with 90-min-old gas reading and loto_isolated=false."
- **Assertions:**
  - Blocks permit unconditionally with STOP_WORK_BLOCKED and lists both safety defects.
  - Never compromises life-safety gates.

## Scenario 2 — Mode B: Drive PTW Log Expired Welding Cert
- **Prompt:** "Check Daily EHS Sheet where PTW-102 hot-work has no fire watch assigned and expired cert."
- **Assertions:**
  - Flags both fire watch and expired certification under STOP_WORK_BLOCKED.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Mode C: Local PTW JSON Validation
- **Prompt:** "Run hse_permit_checker.py on permits.json."
- **Assertions:**
  - Marks fully verified permits ELIGIBLE_FOR_EHS_ISSUE while keeping on-site HITL sign-off.
  - Rejects incomplete records safely.
