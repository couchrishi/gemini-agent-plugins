# Brand Governance, Campaign Matrix & Localization Studio (`brand-campaign-studio`)

Lints marketing copy against brand voice rules, prohibited claims, and channel limits, validates audience-by-channel multimodal campaign matrices, and audits global localization packs against do-not-translate glossaries. Pairs live `/work` connectors (`Google Drive, Google Docs, Google Sheets, Google Slides, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams), Slack`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Brand Governance & Legal Marketing Reviewer | Screening paid ad copy, landing pages, and press drafts before launch | [`brand-voice-compliance-gate`](skills/brand-voice-compliance-gate/README.md) | `scripts/copy_compliance_linter.py` |
| Global Campaign Operations Manager | Auditing launch deliverables, budget pacing, and channel attribution across multi-region rollouts | [`multimodal-campaign-brief`](skills/multimodal-campaign-brief/README.md) | `scripts/campaign_asset_matrix.py` |
| Localization Program Manager | Validating `ja-JP`, `de-DE`, and `fr-FR` campaign translations before regional release | [`market-localization-adapter`](skills/market-localization-adapter/README.md) | `scripts/locale_glossary_checker.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`brand-campaign-studio.zip`](../../dist/bundles/brand-campaign-studio.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/brand-voice-compliance-gate.zip`](../../dist/skills/brand-voice-compliance-gate.zip) — Lints marketing copy for banned guarantees, missing substantiation disclaimers, readability density, and channel char caps.
  - [`dist/skills/multimodal-campaign-brief.zip`](../../dist/skills/multimodal-campaign-brief.zip) — Audits audience-by-channel and funnel coverage matrices, planned spend vs budget, and critical-path launch buffers.
  - [`dist/skills/market-localization-adapter.zip`](../../dist/skills/market-localization-adapter.zip) — Verifies target locale translations for missing markets, untranslated leaks, DNT term preservation, and regional glossary fidelity.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`brand-campaign-studio.zip`](../../dist/bundles/brand-campaign-studio.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/brand-campaign-studio` / `@brand-campaign-studio` so Layer 1 (`remote_cli mcp`) pulls live data from `Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack` or `Localization TMS & Brand CMS MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Brand_Campaign_and_Locale_Sample.xlsx` (`5,162 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Copy_Compliance_Assets`, `Campaign_Deliverables`, `Locale_Translations`, `Glossary_Terms`)](../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx):

```bash
python3 plugins/brand-campaign-studio/skills/brand-voice-compliance-gate/scripts/copy_compliance_linter.py \
  --input examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx \
  --config plugins/brand-campaign-studio/skills/brand-voice-compliance-gate/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack`.
- **Customer BYO-MCP Servers**: `Localization TMS & Brand CMS MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Query Google Drive, SharePoint, and Docs via remote_cli mcp or Workspace tools to pull brand guidelines, campaign copy decks, and locale translation sheets before running copy and glossary lint checks in Python.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Brand_Campaign_and_Locale_Sample.xlsx` (`5,162 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Copy_Compliance_Assets`, `Campaign_Deliverables`, `Locale_Translations`, `Glossary_Terms`)](../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`commercial-contract-baseline.md`](../../shared/baselines/commercial-contract-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md), [`sharepoint-onedrive-kql-traps.md`](../../shared/traps/sharepoint-onedrive-kql-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Publishing public campaign copy or paid ad assets via CMS MCP or shared workspace channels; Sending external agency creative briefs or translation sign-offs over email or Slack.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Unverified superlative, ROI, and missing mandatory claim disclaimer blocker; Strict Do-Not-Translate (DNT) brand glossary and channel character-limit enforcement; Brand color/tone deviation and critical-path campaign dependency cycle checks.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly Campaign Compliance Sweep" on cron `0 10 * * 2` (`UTC`) with instruction: "Run the weekly marketing compliance sweep via scripts/copy_compliance_linter.py across upcoming campaign drafts and flag missing disclaimers or prohibited claims.""*

## Example Queries & Verified Outcomes

- **`brand-voice-compliance-gate`** ([skill guide](skills/brand-voice-compliance-gate/README.md)): Connector prompt: *"Lint Northstar Retail's seasonal Google Docs ad copy claiming 'Save up to 40% with zero risk'."* Verified starter check against `Apex_Brand_Campaign_and_Locale_Sample.xlsx` (`145.2 ms`): `assets_linted=3`, `blocked_count=1`, `warnings_count=0`, `approved_count=2`.
- **`multimodal-campaign-brief`** ([skill guide](skills/multimodal-campaign-brief/README.md)): Connector prompt: *"Audit Meridian BioPharma Q4 launch plan in Drive for missing Conversion stage assets and budget overrun."* Verified starter check against `Apex_Brand_Campaign_and_Locale_Sample.xlsx` (`142.8 ms`): `deliverable_count=3`, `approved_deliverables=0`, `total_budget_usd=450000.0`, `planned_spend_usd=515000.0`.
- **`market-localization-adapter`** ([skill guide](skills/market-localization-adapter/README.md)): Connector prompt: *"Audit Veloce SuperApp regional packs in Smartling where ja-JP translated 'Gemini Enterprise' literally."* Verified starter check against `Apex_Brand_Campaign_and_Locale_Sample.xlsx` (`139.3 ms`): `target_locales_count=3`, `passed_count=2`, `missing_locale_count=0`, `rework_required_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-05`** (`5 tabs, 5,112 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (1.000 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.888 / 1.000`) and `Prose-Only Baseline` (`FAIL 0.357 / 0.000`). Verified domain traps: Superlative/unverified compliance claims in copy asset AD-APX-1642; $65k budget overrun & post-launch critical path slip; Do-Not-Translate and glossary violations in ja-JP localization; 40/20/40 U-shaped attribution net of refunds.
