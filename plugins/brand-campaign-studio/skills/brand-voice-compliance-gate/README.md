# Brand Voice & Claims Compliance Gate (`brand-voice-compliance-gate`)

Lints ad and campaign copy against prohibited claims, mandatory legal disclaimers, sentence readability, and channel character budgets. Deterministic computation executes via [`scripts/copy_compliance_linter.py`](scripts/copy_compliance_linter.py). Domain guards enforced: Blocks prohibited superlatives and missing claim disclaimers; Checks channel-specific headline character caps. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Brand Governance & Legal Marketing Reviewer**: Triggered when screening paid ad copy, landing pages, and press drafts before launch; flags unverified superlatives (`#1`, `guaranteed`), banned phrases, and overlong readability (`>22` words/sentence).
- **Demand Gen Copy Lead**: Triggered when auditing campaign creative batches against regulatory substantiation rules; holds unapproved compliance claims before ad-manager publication.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`brand-voice-compliance-gate.zip`](../../../../dist/skills/brand-voice-compliance-gate.zip) (or the full department bundle [`brand-campaign-studio.zip`](../../../../dist/bundles/brand-campaign-studio.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack` + Customer BYO-MCP (`Localization TMS & Brand CMS MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/brand-voice-compliance-gate` or `@brand-voice-compliance-gate`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.copy_compliance_linter import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"assets": [{"asset_id": r.get("Custom asset_id"), "body": r.get("Custom body")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/brand-campaign-studio/skills/brand-voice-compliance-gate/scripts/copy_compliance_linter.py \
  --input examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx \
  --config plugins/brand-campaign-studio/skills/brand-voice-compliance-gate/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `copy_compliance_linter.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack` + Customer BYO-MCP (`Localization TMS & Brand CMS MCP server`) via `remote_cli mcp`):** "Lint Northstar Retail's seasonal Google Docs ad copy claiming 'Save up to 40% with zero risk'."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Search Ad headlines in Marketing Drive Sheet exceeding 30 characters."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx) and ask: "Screen all marketing copy assets in `Apex_Brand_Campaign_and_Locale_Sample.xlsx` against brand voice, readability, and claims-substantiation guardrails, blocking any unsubstantiated percentage savings or ROI promises from CMS release."

## Sample Response

### What You See in Gemini Enterprise Chat

Linting `3` marketing assets (`90.0 / 100` average compliance score) in `Apex_Brand_Campaign_and_Locale_Sample.xlsx` **approved `2` assets (`AD-APX-1715` paid search and `AD-APX-1720` webinar email, `100 / 100`)** and **blocked `1` LinkedIn draft (`AD-APX-1642`, score `70`)** for missing an unsubstantiated percentage/ROI disclaimer.

- **Blocked Asset (`AD-APX-1642` — `linkedin_post`, Score `70`):** `BLOCKED_COMPLIANCE_VIOLATION` triggered on `'up to %'` / ROI financial claim missing required substantiation footnote.
- **Publication-Ready Assets (`2`):** `AD-APX-1715` (`paid_search`) and `AD-APX-1720` (`webinar_email`) scored `100` (`APPROVED_FOR_LOCALIZATION`).
- **Approval Confirmation Prompt:** Confirm if you would like to publish the `2` clean assets (`AD-APX-1715`, `AD-APX-1720`) via your connected CMS / brand distribution connector (gated by `Auto-Guardian`); `AD-APX-1642` stays held pending legal disclaimer addition.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx) (`145.2 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Brand Voice & Claims Compliance Gate

- **Assets Linted:** 3 | **Blocked:** 1 | **Approved:** 2 | **Avg Score:** 90.0/100

| Asset | Channel | Score | Gate | Findings |
| :--- | :--- | ---: | :--- | :--- |
| `AD-APX-1642` | `linkedin_post` | 70 | `BLOCKED_COMPLIANCE_VIOLATION` | Substantiation claim ('up to %' / ROI / financial rate) missing required disclaimer. |
| `AD-APX-1715` | `paid_search` | 100 | `APPROVED_FOR_LOCALIZATION` | Clean |
| `AD-APX-1720` | `webinar_email` | 100 | `APPROVED_FOR_LOCALIZATION` | Clean |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Campaign Compliance Sweep` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Campaign Compliance Sweep" on cron `0 10 * * 2` (`UTC`) with instruction: "Run the weekly marketing compliance sweep via scripts/copy_compliance_linter.py across upcoming campaign drafts and flag missing disclaimers or prohibited claims."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `assets`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `assets` requires [`asset_id` or `headline` or `body`; `body` or `headline` or `channel`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_avg_sentence_words` | `integer` | `22` | Target maximum average words per sentence in ad/landing copy. |

See [`../../README.md`](../../README.md) for the `brand-campaign-studio` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
