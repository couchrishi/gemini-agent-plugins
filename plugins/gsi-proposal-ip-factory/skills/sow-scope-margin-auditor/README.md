# SOW Scope Creep & Margin Auditor (`sow-scope-margin-auditor`)

Audits Statement of Work deliverables and commercial clauses for unbounded scope creep language, missing objective acceptance criteria, extended milestone acceptance windows, and margin breaches. Deterministic computation executes via [`scripts/sow_margin_linter.py`](scripts/sow_margin_linter.py). Domain guards enforced: Flags missing deliverable acceptance_criteria rather than assuming covered; Catches unbounded scope creep phrasing deterministically. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Consulting Commercial Counsel / Engagement Partner**: Triggered when auditing Statements of Work before signature to eliminate uncapped scope creep; detects unlimited-revision clauses, short deemed-acceptance windows (`<=5d` vs `10d`), and undefined acceptance criteria (`DLV-DATA-HUB`).
- **Delivery Governance Lead**: Triggered when reconciling fixed-fee SOW commercials against bottom-up cost estimates; blocks sub-floor (`<20%` or `<30%`) margin commitments and unpriced change-request obligations.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`sow-scope-margin-auditor.zip`](../../../../dist/skills/sow-scope-margin-auditor.zip) (or the full department bundle [`gsi-proposal-ip-factory.zip`](../../../../dist/bundles/gsi-proposal-ip-factory.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & PSA Staffing MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/sow-scope-margin-auditor` or `@sow-scope-margin-auditor`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.sow_margin_linter import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"deliverables": [{"deliverable_id": r.get("Custom deliverable_id"), "acceptance_criteria": r.get("Custom acceptance_criteria")} for r in wb["Source_Tab"]], "clauses": wb["clauses"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/gsi-proposal-ip-factory/skills/sow-scope-margin-auditor/scripts/sow_margin_linter.py \
  --input examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx \
  --config plugins/gsi-proposal-ip-factory/skills/sow-scope-margin-auditor/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `sow_margin_linter.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & PSA Staffing MCP server`) via `remote_cli mcp`):** "Audit CivicFirst Agency SOW draft containing 'all work required at no additional cost regardless' and 18% margin."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check SOW Doc in Drive with a 20-day acceptance window and 2 deliverables lacking criteria."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx) and ask: "Audit Statement of Work `SOW-APX-GSI-2026-09` in `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` for uncapped revision obligations, missing deliverable acceptance criteria, deemed-acceptance timelines, and fixed-fee gross margin floor breaches."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing **`SOW-APX-GSI-2026-09`** (`$1,850,000.00` fixed fee vs. `$1,420,000.00` estimated cost) in `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` **blocked signature (`BLOCKED_SCORE_9`)** due to **`1` Score-9 unlimited-revisions scope trap (`CL-SOW-01`)**, **`23.24%` blended gross margin** below the `30%` target, and missing acceptance criteria on **`DLV-DATA-HUB`**.

- **Walk-Away Scope Blocker (`CL-SOW-01`):** Grants unlimited client revisions without change-order fee recovery.
- **Negotiable Commercial & Acceptance Warnings (`2`):** `23.24%` gross margin violates the `30%` standard floor (`Score 3`), and deliverable `DLV-DATA-HUB` omits objective exit/acceptance criteria.
- **Approval Confirmation Prompt:** SOW submission is held (`BLOCKED_SCORE_9`); remediate `CL-SOW-01` and `DLV-DATA-HUB` first before requesting Partner approval via your connected PSA / Deal Review connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx) (`139.5 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# SOW Scope Creep & Margin Audit — `SOW-APX-GSI-2026-09`

- **Fixed Fee:** $1,850,000.00 | **Est Cost:** $1,420,000.00 | **Gross Margin:** 23.24% | **Gate:** `BLOCKED_SCORE_9`
- **Score-9 Blockers:** 1 | **Negotiable Warnings:** 2

## Walk-Away Scope/Margin Blockers
- Clause CL-SOW-01: Unlimited revisions/changes clause

## Redline Warnings
- SOW gross margin 23.2% sits below 30% standard target (Score 3).
- Deliverable DLV-DATA-HUB lacks objective acceptance criteria.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Bench Utilization Digest` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Bench Utilization Digest" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly bench-to-demand skill matching check via scripts/talent_bench_matcher.py and surface unfilled roles needing subcontractor sourcing."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `sow_id`, `fixed_fee_usd`, `estimated_cost_usd`, `acceptance_business_days`, `clauses`, `deliverables`, `client_dependencies`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `deliverables` requires [`deliverable_id`; `acceptance_criteria` or `title`] | `clauses` requires [`clause_id` or `text`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_sow_gross_margin_pct` | `number` | `30.0` | Target consulting SOW gross margin percentage floor. |
| `critical_margin_floor_pct` | `number` | `20.0` | Walk-away Score-9 SOW gross margin floor. |
| `max_acceptance_business_days` | `integer` | `10` | Maximum milestone acceptance SLA before deemed accepted. |

See [`../../README.md`](../../README.md) for the `gsi-proposal-ip-factory` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
