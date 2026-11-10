---
name: market-localization-adapter
description: "Validates multi-locale marketing adaptations against do-not-translate terms, approved terminology glossaries, missing locales, and untranslated English leaks Use when QA-checking localized regional copy before international campaign launch. Don't use for scoring English brand compliance before translation (use brand-voice-compliance-gate)."
created_by: gemini-agent-plugins
---

# Market Localization & Glossary Adapter

Prevent literal English leaks, translated protected brand names, and omitted target locales across global launches.

## Three-Mode Connector Degradation

| Mode | Source Path | Execution Guidance |
| :--- | :--- | :--- |
| **Mode A — Live Enterprise Connectors** | `smartling_tms_api, google_drive_api` | Fetch locale translation packs and DNT glossaries from Smartling and Drive. |
| **Mode B — Google Workspace Fallback** | `Google Sheets, Google Docs, Google Drive` | Read Multi-Locale Copy Matrix Sheets and Approved Brand Glossaries in Shared Drives. |
| **Mode C — Direct File Upload** | `.json`, `.csv` | Load localization JSON payloads in Python RAM (read inputs with `view_file`). |

## Org Configuration & Starter Baseline Rule

1. Inspect [config.json](references/config.json) with `view_file`.
2. Whenever `org_configured` is `false`, evaluate strictly against [commercial-contract-baseline.md](references/baselines/commercial-contract-baseline.md) and stamp every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

## In-Memory Python Execution (`pyrepl` & CLI)

Execute [locale_glossary_checker.py](scripts/locale_glossary_checker.py) inside persistent `pyrepl` and optionally emit structured cards via `emit_a2ui` or schedule recurring checks via `schedule_task`:

```python
from scripts.locale_glossary_checker import analyze, render_markdown

res = analyze("input.json", config="references/config.json")
print(render_markdown(res))
```

CLI fallback:

```bash
python3 scripts/locale_glossary_checker.py --input input.json --config references/config.json --format markdown
```

## Enterprise Traps & HITL Confirmation Gate

- Follow [absent-is-not-zero.md](references/traps/absent-is-not-zero.md), [google-workspace-traps.md](references/traps/google-workspace-traps.md), [sharepoint-onedrive-kql-traps.md](references/traps/sharepoint-onedrive-kql-traps.md), [untrusted-content-and-pii.md](references/traps/untrusted-content-and-pii.md).
- Missing target locales MUST be labeled `MISSING_LOCALE_TRANSLATION` and modified DNT product strings MUST fail QA.
- Submitting localization approvals to regional CMS or agency portals requires Regional Marketing confirmation (HITL).
