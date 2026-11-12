# Test Scenarios: `grant-accreditation-evidence-pack`

## Scenario 1 — Live Enterprise Connectors: Sponsored Grant F&A Cap & Unallowable Audit
- **Prompt:** "Audit Cascade State University grant packet with $4k lobbying line, excess F&A above 52% MTDC, and 115% PI effort."
- **Assertions:**
  - Flags UNALLOWABLE_COST_CATEGORY, FA_CAP_EXCEEDED, and PI_OVERALLOCATED_GT_100_PCT.
  - Sets submission_readiness=BLOCKED_REMEDIATE_BEFORE_SUBMISSION.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Accreditation Binder Freshness Check
- **Prompt:** "Verify Accreditation Evidence Folder Sheet in Drive with 420-day-old lab safety certification."
- **Assertions:**
  - Flags STALE_EVIDENCE (>365d) alongside cost-share shortfalls.
  - Includes baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Grant Proposal JSON Validation
- **Prompt:** "Run grant_accreditation_validator.py on grant_packet.json."
- **Assertions:**
  - Computes exact MTDC base and max_allowed_indirect_usd.
  - Maintains Sponsored Programs HITL submission gate.
