# Bench Skill & Project Demand Matcher (`bench-skill-demand-matcher`)

Matches open project role requirements against available bench talent using deterministic skill overlap %, start-date delay limits, and hourly gross margin ranking. Deterministic computation executes via [`scripts/talent_bench_matcher.py`](scripts/talent_bench_matcher.py). Domain guards enforced: Excludes late bench availability beyond max_start_delay_days; Flags unfilled roles explicitly as EXTERNAL_SUBCONTRACT_REQUIRED. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Resource Management / Workforce Planning Lead**: Triggered when matching open project roles against certified internal bench consultants; enforces clearance parity, availability start-delay ceilings (`<=14d`), and `>=60%` skill overlap (`CON-APX-101/102`).
- **Delivery Practice Manager**: Triggered when deciding between internal redeployment and external subcontractor requisitions; quantifies internal fill rate vs subcontract gap before issuing vendor staffing requisitions.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`bench-skill-demand-matcher.zip`](../../../../dist/skills/bench-skill-demand-matcher.zip) (or the full department bundle [`gsi-proposal-ip-factory.zip`](../../../../dist/bundles/gsi-proposal-ip-factory.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & PSA Staffing MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/bench-skill-demand-matcher` or `@bench-skill-demand-matcher`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.talent_bench_matcher import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"consultants": [{"consultant_id": r.get("Custom consultant_id"), "skills": r.get("Custom skills")} for r in wb["Source_Tab"]], "demands": wb["demands"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/gsi-proposal-ip-factory/skills/bench-skill-demand-matcher/scripts/talent_bench_matcher.py \
  --input examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx \
  --config plugins/gsi-proposal-ip-factory/skills/bench-skill-demand-matcher/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `talent_bench_matcher.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & PSA Staffing MCP server`) via `remote_cli mcp`):** "Match Cascade State University project demands against Workday bench roster where SAP Basis lacks local coverage."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check Drive Bench Sheet filtering out consultants rolling off > 21 days after start date."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx) and ask: "Match the open project staffing demands against available internal bench consultants in `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`, enforcing clearance parity, start-delay limits, and minimum skill-overlap rules."

## Sample Response

### What You See in Gemini Enterprise Chat

Screening `3` bench consultants against `2` priority project roles in `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` **`MATCHED_INTERNAL_BENCH` for both demands (`2 / 2`, `0` external subcontracts required)** with `100.0%` skill match and `>53%` delivery margin.

- **`ROLE-BQ-801` (Meridian Sovereign Data Platform):** Matched `Priya Nair` (`CON-APX-101`) at `100.0%` skill overlap and `53.1%` gross margin.
- **`ROLE-K8S-802` (Apex Checkout Resilience Wave 2):** Matched `Arjun Mehta` (`CON-APX-102`) at `100.0%` skill overlap and `55.2%` gross margin.
- **Approval Confirmation Prompt:** Confirm if you would like to reserve `Priya Nair` (`CON-APX-101`) and `Arjun Mehta` (`CON-APX-102`) to their respective PSA project demands via your connected PSA / HRIS staffing connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx`](../../../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx) (`135.4 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Bench Talent & Project Demand Match Report

- **Open Demands:** 2 | **Internal Match:** 2 | **Subcontract Gaps:** 0

| Role ID | Project | Status | Top Candidate | Match % | Margin % |
| :--- | :--- | :--- | :--- | ---: | ---: |
| `ROLE-BQ-801` | Meridian Sovereign Data Platform | `MATCHED_INTERNAL_BENCH` | Priya Nair (`CON-APX-101`) | 100.0% | 53.1% |
| `ROLE-K8S-802` | Apex Checkout Resilience Wave 2 | `MATCHED_INTERNAL_BENCH` | Arjun Mehta (`CON-APX-102`) | 100.0% | 55.2% |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Bench Utilization Digest` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Bench Utilization Digest" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly bench-to-demand skill matching check via scripts/talent_bench_matcher.py and surface unfilled roles needing subcontractor sourcing."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `demands`, `consultants`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `consultants` requires [`consultant_id`; `skills`] | `demands` requires [`role_id`; `required_skills`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_skill_overlap_pct` | `number` | `60.0` | Minimum skill match % for bench candidate shortlisting. |
| `max_start_delay_days` | `integer` | `14` | Maximum acceptable bench availability delay in days. |

See [`../../README.md`](../../README.md) for the `gsi-proposal-ip-factory` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
