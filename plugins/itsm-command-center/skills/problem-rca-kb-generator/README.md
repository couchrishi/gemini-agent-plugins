# Problem RCA & KCS Deflection Generator (`problem-rca-kb-generator`)

Groups repeat resolved incidents into Problem candidates, calculates mean/p90 MTTR and annualized L1 deflection savings, and validates KCS KB completeness. Deterministic computation executes via [`scripts/kcs_deflection_analyzer.py`](scripts/kcs_deflection_analyzer.py). Domain guards enforced: Excludes resolved_at=null and canceled tickets from closed MTTR calculations; Verifies all 5 KCS draft sections before allowing publish readiness. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Problem Management Lead**: Triggered when mining closed incident backlogs for recurring root causes; ranks problem candidates by annual L1 ticket deflection ROI (`cost_per_l1_ticket_usd`) and drafts KCS fixes.
- **Knowledge-Centered Service (KCS) Editor**: Triggered when validating draft resolution articles prior to external portal publication; enforces KCS completeness gates (`environment`, `root_cause`, `workaround`, `resolution`).

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`problem-rca-kb-generator.zip`](../../../../dist/skills/problem-rca-kb-generator.zip) (or the full department bundle [`itsm-command-center.zip`](../../../../dist/bundles/itsm-command-center.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/problem-rca-kb-generator` or `@problem-rca-kb-generator`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.kcs_deflection_analyzer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"tickets": [{"ticket_id": r.get("Custom ticket_id"), "category": r.get("Custom category")} for r in wb["Source_Tab"]], "kcs_drafts": wb["kcs_drafts"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/itsm-command-center/skills/problem-rca-kb-generator/scripts/kcs_deflection_analyzer.py \
  --input examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx \
  --config plugins/itsm-command-center/skills/problem-rca-kb-generator/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `kcs_deflection_analyzer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack` via `remote_cli mcp`):** "Analyze the last 90 days of Apex Manufacturing ServiceNow tickets to identify top Problem candidates and KCS deflection ROI."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Check our draft KCS Google Docs against the ticket summary Sheet in Shared Drive before publishing."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx) and ask: "Mine the historical ticket and KCS draft tabs in `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` to quantify recurring Problem candidates by annual L1 deflection ROI, validate KCS draft completeness, and hold external portal publishing for review."

## Sample Response

### What You See in Gemini Enterprise Chat

Scanning `4` resolved/closed tickets and `2` KCS drafts in `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` identified **`1` recurring Problem candidate (`Auth` / `saml cert expiry`, `3` incidents, `2.50h` mean MTTR)** delivering **`$358.40` estimated annual L1 deflection savings** on this starter slice.

- **Clean Denominator Filtering:** `0` unresolved or canceled noise tickets distorted the MTTR or volume counts across the `4` scanned records.
- **KCS Completeness Gate Verified:** `2` knowledge drafts were checked against mandatory `environment`, `root_cause`, `workaround`, and `resolution` sections before publication.
- **Approval Confirmation Prompt:** Confirm if you would like to publish the validated `saml cert expiry` KCS article to the support portal via your connected `ServiceNow` or `Confluence` portal connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx) (`143.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Problem Candidate & KCS Deflection Analysis

- **Tickets Scanned:** 4 (Excluded open: 0, canceled: 0)
- **Problem Candidates:** 1 | **Estimated Annual L1 Savings:** $358.40

| Category | Root Cause Signature | Count | Mean MTTR (h) | Annual Savings (USD) |
| :--- | :--- | ---: | ---: | ---: |
| Auth | saml cert expiry | 3 | 2.50 | $358.40 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly SLA Breach Watch` routine via `schedule_task`:

```text
Schedule recurring job "Hourly SLA Breach Watch" on cron `0 * * * *` (`UTC`) with instruction: "Execute hourly incident triage and SLA breach scan via scripts/sla_cluster_triage.py. Highlight active P1/P2 tickets above 75% business-elapsed SLA budget, flag emerging CI/error spike clusters, and recommend top matching runbooks without mutating ticket assignments automatically."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `sample_window_days`, `tickets`, `kcs_drafts`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `tickets` requires [`ticket_id`; `category` or `root_cause_signature` or `state`] | `kcs_drafts` requires [`article_id` or `title`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `cost_per_l1_ticket_usd` | `number` | `28.0` | Average unit cost per L1 service desk ticket used to estimate KCS deflection savings. |
| `expected_kcs_deflection_rate` | `number` | `0.35` | Expected fraction of recurring tickets deflected by a published KCS self-service article. |

See [`../../README.md`](../../README.md) for the `itsm-command-center` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
