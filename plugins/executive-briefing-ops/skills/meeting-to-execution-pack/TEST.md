# Test Scenarios: `meeting-to-execution-pack`

## Scenario 1 — Live Enterprise Connectors: Google Meet Transcript & Prior Action Carryover
- **Prompt:** "Convert today's Apex Manufacturing Steering Committee Google Meet transcript into an execution pack and check carryovers against last week's open actions."
- **Assertions:**
  - Extracts owner-assigned actions, decisions, and blockers via `transcript_action_extractor.py`.
  - Increments `carryover_count` on tasks re-raised without closure.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Multi-Tab Google Doc Notes Fallback
- **Prompt:** "Read Tab 1 and Tab 2 of our Q4 Exec Sync Google Doc notes and draft a follow-up email to attendees."
- **Assertions:**
  - Parses all tabs cleanly and drafts follow-up as Gmail draft without sending autonomously.

## Scenario 3 — Optional Local File Sandbox: Raw Unattributed Transcript Upload
- **Prompt:** "Extract tasks from this uploaded raw `.txt` meeting note where speaker prefixes are missing on half the lines."
- **Assertions:**
  - Emits `ATTRIBUTION_WARNING` and marks unowned actions `UNASSIGNED` instead of guessing owners.
  - Stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` when `org_configured: false`.
