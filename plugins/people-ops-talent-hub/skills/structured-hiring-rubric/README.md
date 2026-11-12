# Structured Hiring Rubric Calibration (`structured-hiring-rubric`)

Calibrates structured interview scorecards across 1-4 anchors, flags score dispersion = 2.0, thin evidence, and potential bias phrasing. Deterministic computation executes via [`scripts/rubric_calibration_checker.py`](scripts/rubric_calibration_checker.py). Domain guards enforced: Flags score dispersion >= 2.0 and Score 1 vetoes; Detects bias phrasing and sub-40-char evidence notes. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Recruiting & Talent Bar Lead**: Triggered when calibrating multi-interviewer hiring scorecards prior to hiring committee review; detects interviewer score spread (`>=2.0`), thin evidence (`<40` chars), and subjective bias phrasing.
- **Hiring Manager / Bar Raiser**: Triggered when separating clear hire consensus from debrief-required candidate packets; enforces panel calibration rules before any Workday/Greenhouse offer draft proceeds.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`structured-hiring-rubric.zip`](../../../../dist/skills/structured-hiring-rubric.zip) (or the full department bundle [`people-ops-talent-hub.zip`](../../../../dist/bundles/people-ops-talent-hub.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & ATS Scorecard MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/structured-hiring-rubric` or `@structured-hiring-rubric`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.rubric_calibration_checker import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"candidates": [{"candidate_id": r.get("Custom candidate_id"), "interviewers": r.get("Custom interviewers")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/people-ops-talent-hub/skills/structured-hiring-rubric/scripts/rubric_calibration_checker.py \
  --input examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx \
  --config plugins/people-ops-talent-hub/skills/structured-hiring-rubric/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `rubric_calibration_checker.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & ATS Scorecard MCP server`) via `remote_cli mcp`):** "Calibrate Greenhouse scorecards for Cymbal Financial Staff Engineer candidate with scores [4, 1, 4, 3]."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit the Debrief Doc in Drive containing 'good culture fit, high energy for recent grad' in 25 chars."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx) and ask: "Calibrate the candidate interview scorecards in `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`, flagging wide interviewer score spreads, thin rubric evidence (<40 characters), or subjective bias language before advancing any candidate to offer."

## Sample Response

### What You See in Gemini Enterprise Chat

Auditing `2` candidate packets in `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` **cleared `CAND-APX-805` (`Samira Rao`, Senior SRE, mean `4.00`, `0.0` spread) as `HIRE_RECOMMENDED_FOR_HITL`** while **blocking `CAND-APX-804` (`Jordan Lee`, spread `2.0`, `1` thin-evidence flag)** for debrief remediation.

- **HITL-Ready Candidate:** `Samira Rao` (`CAND-APX-805`) cleared all evidence length, bias-language (`0` flags), and panel agreement checks (`4.00` average).
- **Calibration Block:** `Jordan Lee` (`CAND-APX-804`, Staff Distributed Systems Engineer) triggered `2.0`-point panel score spread plus `1` thin-evidence review (`CALIBRATION_BLOCKED_BIAS_OR_THIN_EVIDENCE`).
- **Approval Confirmation Prompt:** Confirm if you would like to advance `Samira Rao` (`CAND-APX-805`) to Greenhouse offer drafting via your connected ATS / HR MCP server or HRIS workflow (gated by `Auto-Guardian`) while holding `CAND-APX-804` for panel debrief.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx) (`148.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Structured Hiring Rubric & Panel Calibration Audit

- **Candidates Reviewed:** 2 | **Hire Ready (HITL):** 1 | **Debrief Required:** 0 | **Blocked (Bias/Thin Evidence):** 1

| Candidate | Role | Panel | Mean | Spread | Bias Flags | Thin Evidence | Calibration Status |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `CAND-APX-804` Jordan Lee | Staff Distributed Systems Engineer | 2 | 3.00 | 2.0 | 0 | 1 | `CALIBRATION_BLOCKED_BIAS_OR_THIN_EVIDENCE` |
| `CAND-APX-805` Samira Rao | Senior SRE | 2 | 4.00 | 0.0 | 0 | 0 | `HIRE_RECOMMENDED_FOR_HITL` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Onboarding Stall Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Onboarding Stall Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly onboarding gate check via scripts/onboarding_plan_builder.py to detect missing Day-1 IT/security gates and stalled 30/60/90 milestones."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `candidates`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `candidates` requires [`candidate_id` or `candidate_name`; `interviewers` or `interviewer_id` or `score`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `max_score_spread` | `number` | `2.0` | Interviewer score spread alert threshold on 1-4 scale. |
| `min_evidence_chars` | `integer` | `40` | Minimum behavioral evidence length per scorecard. |
| `hire_mean_threshold` | `number` | `3.0` | Minimum panel mean score for hire consensus. |

See [`../../README.md`](../../README.md) for the `people-ops-talent-hub` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
