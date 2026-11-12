# Test Scenarios: `brand-voice-compliance-gate`

## Scenario 1 — Live Enterprise Connectors: Drive Ad Copy Claim Check
- **Prompt:** "Lint Northstar Retail's seasonal Google Docs ad copy claiming 'Save up to 40% with zero risk'."
- **Assertions:**
  - Flags both prohibited claim ('zero risk') and missing disclaimer -> BLOCKED_COMPLIANCE_VIOLATION.
  - Computes compliance_score accurately.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Workspace Search Ad Limit Check
- **Prompt:** "Check Search Ad headlines in Marketing Drive Sheet exceeding 30 characters."
- **Assertions:**
  - Flags character limit warning and lowers compliance_score.
  - Applies baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local JSON Copy Gate
- **Prompt:** "Lint copy_assets.json locally and verify HITL gate before CMS publish."
- **Assertions:**
  - Distinguishes APPROVED_FOR_LOCALIZATION vs BLOCKED assets clearly.
  - Preserves human publish sign-off.
