# Winning Proposal Staffing Pyramid Architect (`winning-proposal-architect`)

Models GSI consulting staffing pyramids across delivery phases, calculates onshore/offshore leverage, blended bill rate, and gross margin against 30%/20% guardrails. Deterministic computation executes via [`scripts/staffing_pyramid_calculator.py`](scripts/staffing_pyramid_calculator.py). Domain guards enforced: Computes weighted blended bill rate and margin across all phase durations; Flags sub-20% critical floor breaches distinctly from 20-30% Finance Desk exceptions. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **GSI Solution Architect / Pursuit Lead**: Triggered when sizing multi-phase delivery pyramids, blended rates, and offshore leverage ratios for enterprise RFPs; distinguishes named delivery phases (`$594,880` / `51.00%` GM / `74.07%` offshore) from synthetic wave lines and checks margin floors.
- **Practice Finance Director**: Triggered when reviewing global delivery mix prior to submitting binding fixed-price bids; verifies blended gross margin stays above target (`>=30%`) and flags under-leveraged onshore pyramids.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`winning-proposal-architect.zip`](../../../../dist/skills/winning-proposal-architect.zip) (or the full department bundle [`gsi-proposal-ip-factory.zip`](../../../../dist/bundles/gsi-proposal-ip-factory.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & PSA Staffing MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/winning-proposal-architect` or `@winning-proposal-architect`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.staffing_pyramid_calculator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"phases": [{"phase_name": r.get("Custom phase_name"), "duration_weeks": r.get("Custom duration_weeks")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/gsi-proposal-ip-factory/skills/winning-proposal-architect/scripts/staffing_pyramid_calculator.py \
  --input examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx \
  --config plugins/gsi-proposal-ip-factory/skills/winning-proposal-architect/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `staffing_pyramid_calculator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & PSA Staffing MCP server`) via `remote_cli mcp`):** "Model Stratos Telecom CRM migration staffing pyramid in Drive with 25% offshore leverage and 26% gross margin."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check our Drive Pricing Pyramid Sheet where discounts dropped gross margin to 18.5%."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx) and ask: "Evaluate the GSI delivery phases and staffing pyramid in the attached `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` workbook, separating core delivery phases from supplemental rows and verifying blended bill rate, offshore leverage, and gross margin targets."

## Sample Response

### What You See in Gemini Enterprise Chat

Across the `3` named delivery phases (`4,320.0` total hours) in `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`, total engagement revenue reaches **`$594,880.00` (`$291,520.00` loaded cost, `$303,360.00` gross profit) at `51.00%` blended gross margin (`WITHIN_MARGIN_TARGET`)**, powered by **`74.07%` offshore leverage** (`$137.70/hr` blended bill rate).

- **Phase Breakdown:** Discovery (`640h`, `50.0%` offshore, `$121.6k`, `48.95%` GM), Core Cloud & Data Migration (`3,360h`, `85.7%` offshore, `$396.48k`, `52.78%` GM), and Cutover & Hypercare (`320h`, `0.0%` offshore, `$76.8k`, `45.00%` GM).
- **Margin & Leverage Targets Passed:** Both blended gross margin (`51.00%` vs `30.0%` floor) and offshore pyramid leverage (`74.07%`) comfortably beat commercial bid floors.
- **Approval Confirmation Prompt:** Confirm if you would like to package and submit this priced staffing model to pursuit bid review via your connected PSA / Deal Review connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx) (`166.0 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# GSI Delivery Staffing Pyramid & Commercial Margin Model

- **Total Revenue:** $594,880.00 | **Loaded Cost:** $291,520.00 | **Gross Margin:** 51.00% (`WITHIN_MARGIN_TARGET`)
- **Total Effort:** 4,320.0 hrs | **Blended Rate:** $137.70/hr | **Offshore Leverage:** 74.1%

| Phase | Weeks | Hours | Offshore % | Revenue | Cost | Margin % |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Discovery & Architecture Blueprint | 4.0 | 640.0 | 50.0% | $121,600.00 | $62,080.00 | 48.95% |
| Core Cloud & Data Migration | 12.0 | 3,360.0 | 85.7% | $396,480.00 | $187,200.00 | 52.78% |
| Cutover & Hypercare | 4.0 | 320.0 | 0.0% | $76,800.00 | $42,240.00 | 45.00% |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Bench Utilization Digest` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Bench Utilization Digest" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly bench-to-demand skill matching check via scripts/talent_bench_matcher.py and surface unfilled roles needing subcontractor sourcing."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `phases`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `phases` requires [`phase_name`; `duration_weeks` or `roles` or `bill_rate_hourly`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_sow_gross_margin_pct` | `number` | `30.0` | Target consulting SOW gross margin percentage floor. |
| `critical_margin_floor_pct` | `number` | `20.0` | Walk-away Score-9 SOW gross margin floor. |
| `target_offshore_leverage_pct` | `number` | `55.0` | Target offshore/nearshore delivery hours share. |

See [`../../README.md`](../../README.md) for the `gsi-proposal-ip-factory` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
