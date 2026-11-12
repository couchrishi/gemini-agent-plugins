# Market Localization & Glossary Adapter (`market-localization-adapter`)

Validates multi-locale marketing adaptations against do-not-translate terms, approved terminology glossaries, missing locales, and untranslated English leaks. Deterministic computation executes via [`scripts/locale_glossary_checker.py`](scripts/locale_glossary_checker.py). Domain guards enforced: Flags missing target locales and literal source-language leaks; Verifies protected do_not_translate_terms stay verbatim. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Localization Program Manager**: Triggered when validating `ja-JP`, `de-DE`, and `fr-FR` campaign translations before regional release; enforces verbatim `Do-Not-Translate` product terms (`Gemini Enterprise`, `BigQuery`, `Vertex AI`) and glossary accuracy.
- **Regional Field Marketing Lead**: Triggered when preventing culturally off-tone or untranslated placeholders from shipping live; blocks incomplete locale packages prior to CMS push.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`market-localization-adapter.zip`](../../../../dist/skills/market-localization-adapter.zip) (or the full department bundle [`brand-campaign-studio.zip`](../../../../dist/bundles/brand-campaign-studio.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack` + Customer BYO-MCP (`Localization TMS & Brand CMS MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/market-localization-adapter` or `@market-localization-adapter`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.locale_glossary_checker import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"translations": [{"locale": r.get("Custom locale"), "translated_text": r.get("Custom translated_text")} for r in wb["Source_Tab"]], "glossary": wb["glossary"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/brand-campaign-studio/skills/market-localization-adapter/scripts/locale_glossary_checker.py \
  --input examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx \
  --config plugins/brand-campaign-studio/skills/market-localization-adapter/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `locale_glossary_checker.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack` + Customer BYO-MCP (`Localization TMS & Brand CMS MCP server`) via `remote_cli mcp`):** "Audit Veloce SuperApp regional packs in Smartling where ja-JP translated 'Gemini Enterprise' literally."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Regional Copy Sheet in Drive where fr-FR is blank and de-DE still holds untranslated English."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx) and ask: "Run terminology, Do-Not-Translate (`Gemini Enterprise`, `Apex Cloud`), and glossary QA checks across all regional translations (`de-DE`, `fr-FR`, `ja-JP`) in `Apex_Brand_Campaign_and_Locale_Sample.xlsx` prior to regional CMS push."

## Sample Response

### What You See in Gemini Enterprise Chat

Validating `3` regional localization packs in `Apex_Brand_Campaign_and_Locale_Sample.xlsx` **passed `de-DE` and `fr-FR` (`LOCALE_QA_PASSED`, `0` violations)** while flagging **`ja-JP` as `LOCALIZATION_REWORK_REQUIRED`** due to Do-Not-Translate breaches (`Gemini Enterprise`, `Apex Cloud`) and glossary mismatch (`reporting`).

- **Cleared Locales (`2 / 3`):** German (`de-DE`) and French (`fr-FR`) preserved every protected brand term and glossary mapping with zero English text leaks.
- **Japanese Rework Held (`ja-JP`):** Altered protected terms (`Gemini Enterprise`, `Apex Cloud`) and missed approved translation `'レポーティング'` for `'reporting'`.
- **Approval Confirmation Prompt:** Confirm if you would like to publish `de-DE` and `fr-FR` via your connected CMS / brand distribution connector (gated by `Auto-Guardian`) while returning `ja-JP` to localization translators.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx) (`139.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Market Localization & Terminology QA Report

- **Target Locales:** 3 | **Passed:** 2 | **Missing:** 0 | **Rework Required:** 1

| Locale | Status | DNT Violations | Glossary Mismatches | Untranslated Leak |
| :--- | :--- | :--- | :--- | :--- |
| `de-DE` | `LOCALE_QA_PASSED` | None | None | No |
| `fr-FR` | `LOCALE_QA_PASSED` | None | None | No |
| `ja-JP` | `LOCALIZATION_REWORK_REQUIRED` | Gemini Enterprise, Apex Cloud | Expected 'レポーティング' for 'reporting'; Expected 'Apex Cloud' for 'Apex Cloud'; Expected 'Gemini Enterprise' for 'Gemini Enterprise' | No |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Campaign Compliance Sweep` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Campaign Compliance Sweep" on cron `0 10 * * 2` (`UTC`) with instruction: "Run the weekly marketing compliance sweep via scripts/copy_compliance_linter.py across upcoming campaign drafts and flag missing disclaimers or prohibited claims."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `source_text`, `target_locales`, `do_not_translate_terms`, `glossary`, `translations`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `translations` requires [`locale`; `translated_text`] | `glossary` requires [`source_term`; `approved_translations`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `required_locales` | `array` | `["ja-JP", "de-DE", "fr-FR"]` | Default target locales expected on global launches. |
| `do_not_translate_terms` | `array` | `["Gemini Enterprise", "BigQuery", "Vertex AI"]` | Protected product terms that must stay verbatim across locales. |

See [`../../README.md`](../../README.md) for the `brand-campaign-studio` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
