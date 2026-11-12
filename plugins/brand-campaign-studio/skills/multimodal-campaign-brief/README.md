# Multimodal Campaign Brief & Asset Matrix (`multimodal-campaign-brief`)

Builds audience-by-channel and funnel deliverable matrices, flags coverage gaps, checks budget caps, and identifies late critical-path assets. Deterministic computation executes via [`scripts/campaign_asset_matrix.py`](scripts/campaign_asset_matrix.py). Domain guards enforced: Explicitly reports uncovered audience-channel and funnel cells; Checks asset due_date lead time against min_production_buffer_days. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Global Campaign Operations Manager**: Triggered when auditing launch deliverables, budget pacing, and channel attribution across multi-region rollouts; computes exact `40/20/40` U-shaped attribution net of refunds, detects `$65k+` overruns, and guards `5`-day pre-launch buffers.
- **Performance Marketing Lead**: Triggered when reconciling paid media spend and creative dependencies against launch dates; prevents self-attributing platform double-counting and highlights critical-path asset delays.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`multimodal-campaign-brief.zip`](../../../../dist/skills/multimodal-campaign-brief.zip) (or the full department bundle [`brand-campaign-studio.zip`](../../../../dist/bundles/brand-campaign-studio.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack` + Customer BYO-MCP (`Localization TMS & Brand CMS MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/multimodal-campaign-brief` or `@multimodal-campaign-brief`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.campaign_asset_matrix import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"deliverables": [{"asset_id": r.get("Custom asset_id"), "estimated_cost_usd": r.get("Custom estimated_cost_usd")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/brand-campaign-studio/skills/multimodal-campaign-brief/scripts/campaign_asset_matrix.py \
  --input examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx \
  --config plugins/brand-campaign-studio/skills/multimodal-campaign-brief/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `campaign_asset_matrix.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Slack` + Customer BYO-MCP (`Localization TMS & Brand CMS MCP server`) via `remote_cli mcp`):** "Audit Meridian BioPharma Q4 launch plan in Drive for missing Conversion stage assets and budget overrun."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Drive Launch Tracker Sheet for assets due only 2 days before launch_date."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx) and ask: "Evaluate the Q4 integrated campaign launch brief in `Apex_Brand_Campaign_and_Locale_Sample.xlsx` for budget vs. planned spend variance, critical-path lead-time slippage, and Audience x Channel or Funnel coverage gaps."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing *Q4 Apex Enterprise Cloud Launch* (`2026-12-15` launch) in `Apex_Brand_Campaign_and_Locale_Sample.xlsx` flagged **`LAUNCH_AT_RISK_GAPS_PRESENT` (`0 / 3` deliverables approved)**: planned spend (`$515,000.00`) **exceeds budget (`$450,000.00`) by `+$65,000.00`**, with **`6` Audience x Channel gaps**, **`9` funnel gaps**, and **`1` late critical-path asset**.

- **Budget Overrun:** Planned media/creative allocation runs `$65,000.00` (`+14.4%`) over the `$450,000.00` approved cap (`over_budget: True`).
- **Missing Matrix Coverage (`6` Audience x Channel cells):** Uncovered combinations span `CFO x Webinar/Search`, `CIO x LinkedIn/Search`, and `CISO x LinkedIn/Webinar`, plus `1` late critical-path asset inside the pre-launch buffer.
- **Approval Confirmation Prompt:** Confirm campaign budget reallocation before pushing any approved launch creative live via your connected CMS / brand distribution connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Brand_Campaign_and_Locale_Sample.xlsx`](../../../../examples/brand-campaign-studio/Apex_Brand_Campaign_and_Locale_Sample.xlsx) (`142.8 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Multimodal Campaign Matrix — Q4 Apex Enterprise Cloud Launch (Launch 2026-12-15)

- **Readiness:** `LAUNCH_AT_RISK_GAPS_PRESENT` | **Deliverables:** 3 (Approved: 0)
- **Planned Spend:** $515,000.00 vs **Budget:** $450,000.00 (Var: $+65,000.00)
- **Matrix Gaps:** 6 Audience×Channel | 9 Funnel Stage | **Late Assets (< buffer):** 1

## Missing Audience × Channel Coverage
- `CFO` × `Webinar`
- `CFO` × `Search`
- `CIO` × `LinkedIn`
- `CIO` × `Search`
- `CISO` × `LinkedIn`
- `CISO` × `Webinar`
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Campaign Compliance Sweep` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Campaign Compliance Sweep" on cron `0 10 * * 2` (`UTC`) with instruction: "Run the weekly marketing compliance sweep via scripts/copy_compliance_linter.py across upcoming campaign drafts and flag missing disclaimers or prohibited claims."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `campaign_name`, `total_budget_usd`, `launch_date`, `target_audiences`, `channels`, `deliverables`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `deliverables` requires [`asset_id` or `channel`; `estimated_cost_usd` or `due_date` or `audience`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_production_buffer_days` | `integer` | `5` | Minimum calendar days between asset completion and campaign launch. |

See [`../../README.md`](../../README.md) for the `brand-campaign-studio` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
