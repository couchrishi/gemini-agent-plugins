# Test Scenarios: `market-localization-adapter`

## Scenario 1 — Live Enterprise Connectors: TMS Glossary & DNT Check
- **Prompt:** "Audit Veloce SuperApp regional packs in Smartling where ja-JP translated 'Gemini Enterprise' literally."
- **Assertions:**
  - Flags dnt_violations containing 'Gemini Enterprise' -> LOCALIZATION_REWORK_REQUIRED.
  - Detects glossary term mismatches.

## Scenario 2 — Connected Google Workspace / Microsoft 365: Drive Sheet Missing fr-FR Column
- **Prompt:** "Check Regional Copy Sheet in Drive where fr-FR is blank and de-DE still holds untranslated English."
- **Assertions:**
  - Flags fr-FR as MISSING_LOCALE_TRANSLATION and de-DE untranslated_leak=true.
  - Emits baseline banner when org_configured is false.

## Scenario 3 — Optional Local File Sandbox: Local Translation JSON QA
- **Prompt:** "Run locale_glossary_checker.py on localization_pack.json."
- **Assertions:**
  - Passes compliant locales cleanly and isolates rework locales.
  - Respects HITL gate for CMS release.
