# Workforce Attrition & Compa-Ratio Audit (`workforce-attrition-comp-audit`)

Audits Workday compensation bands and departmental attrition after deduplicating effective-dated rows, separating contractors, normalizing pay frequencies, and suppressing small cells under n=5. Deterministic computation executes via [`scripts/comp_band_analyzer.py`](scripts/comp_band_analyzer.py). Domain guards enforced: Deduplicates effective_date <= as_of_date per worker_id; Suppresses avg_compa_ratio and attrition_pct when fte_headcount < 5. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Compensation Committee / Total Rewards Lead**: Triggered when running annual pay-equity, compa-ratio, and attrition audits across global entities; deduplicates historical `effective_date` rows, isolates `CWK` contractors, normalizes EUR/monthly pay, and enforces strict `n < 5` cohort suppression.
- **HR Business Partner (HRBP)**: Triggered when identifying below-band compression (`<0.80`) or above-ceiling comp outliers (`>1.25` / `EMP-APX-2110`); prevents accidental individual PII salary leaks in executive summaries via structural cohort gating.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`workforce-attrition-comp-audit.zip`](../../../../dist/skills/workforce-attrition-comp-audit.zip) (or the full department bundle [`people-ops-talent-hub.zip`](../../../../dist/bundles/people-ops-talent-hub.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & ATS Scorecard MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/workforce-attrition-comp-audit` or `@workforce-attrition-comp-audit`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.comp_band_analyzer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"workers": [{"worker_id": r.get("Custom worker_id"), "job_level": r.get("Custom job_level")} for r in wb["Source_Tab"]], "comp_bands": wb["comp_bands"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/people-ops-talent-hub/skills/workforce-attrition-comp-audit/scripts/comp_band_analyzer.py \
  --input examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx \
  --config plugins/people-ops-talent-hub/skills/workforce-attrition-comp-audit/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `comp_band_analyzer.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & ATS Scorecard MCP server`) via `remote_cli mcp`):** "Audit Workday roster where promoted employees have 3 historical effective_date rows plus 1 future-dated row and 4 CWKs."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check department compa-ratios from Drive Sheet where Legal has 3 FTEs and Engineering has hourly + EUR staff."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx) and ask: "Audit the employee compensation and attrition census in `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` as of `2026-11-10`: deduplicate historical `effective_date` rows, isolate `CWK` contractors, flag compression (<0.80) and above-ceiling (>1.25) outliers, and enforce strict `n < 5` department privacy suppression."

## Sample Response

### What You See in Gemini Enterprise Chat

Processing `17` raw rows in `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` collapsed `1` historical snapshot and isolated `1` contingent worker (`CWK`) to leave **`15` unique FTEs (`14` active, `1.049` overall active compa-ratio, `5` comp outliers)** while structurally **`REDACTED (n<5)` suppressing `2` small departments (`Corporate Strategy` `n=4`, `Legal & Privacy` `n=3`)**.

- **Zero Individual PII Leakage:** `Corporate Strategy` (`4` FTEs) and `Legal & Privacy` (`3` FTEs) were redacted inside Python serialization (`0` individual salary leaks), while `Cloud Engineering` (`8` FTEs, `1.066` avg compa-ratio, `12.5%` attrition) reported cleanly.
- **Comp Outliers Detected:** `5` active FTEs fell outside `[0.80, 1.25]` compa-ratio guardrails for Total Rewards review.
- **Approval Confirmation Prompt:** Confirm if you would like to stage band-adjustment proposals for the `5` outlier records via your connected Workday HRIS MCP server (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx) (`161.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Workforce Compensation & Attrition Audit (As Of 2026-11-10)

- **Unique FTEs:** 15 (Active: 14) | **CWK Contractors Isolated:** 1 | **Historical Snapshots Collapsed:** 1
- **Overall Active Avg Compa-Ratio:** 1.049 | **Outliers:** 5 | **Privacy-Suppressed Depts (n < 5):** 2

| Department | FTE Count | Avg Compa-Ratio | Attrition % | Privacy Suppressed |
| :--- | ---: | ---: | ---: | :--- |
| Cloud Engineering | 8 | 1.066 | 12.5% | No |
| Corporate Strategy | 4 | REDACTED (n<5) | REDACTED (n<5) | YES |
| Legal & Privacy | 3 | REDACTED (n<5) | REDACTED (n<5) | YES |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Onboarding Stall Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Onboarding Stall Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly onboarding gate check via scripts/onboarding_plan_builder.py to detect missing Day-1 IT/security gates and stalled 30/60/90 milestones."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `fx_rates`, `comp_bands`, `workers`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `workers` requires [`worker_id`; `job_level` or `base_pay_amount` or `base_pay`] | `comp_bands` requires [`job_level`; `midpoint_usd`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `compa_ratio_min` | `number` | `0.85` | Lower target compa-ratio bound. |
| `compa_ratio_max` | `number` | `1.15` | Upper target compa-ratio bound. |
| `compa_ratio_underpaid_alert` | `number` | `0.8` | Below-band compression alert threshold. |
| `compa_ratio_overpaid_alert` | `number` | `1.25` | Above-band ceiling alert threshold. |
| `min_privacy_cell_size` | `integer` | `5` | Minimum FTE cohort size before suppressing group comp/attrition metrics. |
| `annual_working_hours` | `integer` | `2080` | Standard annual hours for hourly-to-annual pay normalization. |

See [`../../README.md`](../../README.md) for the `people-ops-talent-hub` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
