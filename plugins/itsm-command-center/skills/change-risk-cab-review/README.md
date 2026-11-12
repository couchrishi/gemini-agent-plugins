# Change Risk & CAB Review (`change-risk-cab-review`)

Scores ServiceNow and Jira Change Requests on a 0-100 CAB rubric covering blast radius, tested rollback, freeze-window collisions, and CI failure history. Deterministic computation executes via [`scripts/cab_risk_scorer.py`](scripts/cab_risk_scorer.py). Domain guards enforced: Detects blackout freeze-window timestamp overlaps deterministically; Penalizes missing tested rollback scripts and non-reversible migrations. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Change Advisory Board (CAB) Chair**: Triggered when evaluating production database, payment, or Tier-0 changes ahead of deployment windows; blocks freeze-window collisions (`CHG-APX-9042`) and high-risk changes missing tested rollback scripts.
- **Release Engineering Lead**: Triggered when pre-screening emergency CAB requests during peak holiday traffic; computes objective risk scores (`>=60` block floor) before opening ServiceNow change approval.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`change-risk-cab-review.zip`](../../../../dist/skills/change-risk-cab-review.zip) (or the full department bundle [`itsm-command-center.zip`](../../../../dist/bundles/itsm-command-center.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/change-risk-cab-review` or `@change-risk-cab-review`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.cab_risk_scorer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"changes": [{"change_id": r.get("Custom change_id"), "cmdb_ci": r.get("Custom cmdb_ci")} for r in wb["Source_Tab"]], "freeze_windows": wb["freeze_windows"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/itsm-command-center/skills/change-risk-cab-review/scripts/cab_risk_scorer.py \
  --input examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx \
  --config plugins/itsm-command-center/skills/change-risk-cab-review/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `cab_risk_scorer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack` via `remote_cli mcp`):** "Score Stratos Telecom's pending Thursday night ServiceNow changes against the Q4 Freeze Window calendar."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Evaluate the pending Jira/ServiceNow changes listed in our Shared Drive CAB Prep Sheet."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx) and ask: "Score the pending change requests in `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` against our holiday freeze calendar, rollback test requirements, and blast-radius rules, and block any high-risk collisions from auto-approval."

## Sample Response

### What You See in Gemini Enterprise Chat

Evaluating `2` change requests in `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` surfaced **`1` severe CAB blocker (`CHG-APX-9042`, risk score `85`)** colliding with a change freeze window without a tested rollback, alongside `1` low-risk standard change (`CHG-APX-9045`, score `28`).

- **HOLD (`CHG-APX-9042` — `payments-core`, Score `85`):** Blocked due to active freeze collision (`True`) and missing tested rollback (`False`); requires **Emergency / Executive VP + SRE Lead Sign-Off**.
- **Eligible Standard (`CHG-APX-9045` — `edge-proxy`, Score `28`):** Clean freeze check (`False`) with verified tested rollback (`True`).
- **Approval Confirmation Prompt:** Confirm whether to approve `CHG-APX-9045` and reject/defer `CHG-APX-9042` via your connected `ServiceNow` CAB connector (gated by `Auto-Guardian`) — explicit user confirmation required for `score >= 30` or freeze collisions.

### Verified Deterministic Engine Output

Executed directly against [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx) (`157.6 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# CAB Change Risk Review

- **Changes Scored:** 2 | **High/Emergency:** 1 | **Freeze Collisions:** 1

| Change ID | CI | Score | CAB Routing Tier | Freeze Collision | Tested Rollback |
| :--- | :--- | ---: | :--- | :---: | :---: |
| `CHG-APX-9042` | payments-core | 85 | Emergency / Executive VP + SRE Lead Sign-Off | `True` | `False` |
| `CHG-APX-9045` | edge-proxy | 28 | Standard / Auto-Approve Eligible | `False` | `True` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly SLA Breach Watch` routine via `schedule_task`:

```text
Schedule recurring job "Hourly SLA Breach Watch" on cron `0 * * * *` (`UTC`) with instruction: "Execute hourly incident triage and SLA breach scan via scripts/sla_cluster_triage.py. Highlight active P1/P2 tickets above 75% business-elapsed SLA budget, flag emerging CI/error spike clusters, and recommend top matching runbooks without mutating ticket assignments automatically."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `freeze_windows`, `changes`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `changes` requires [`change_id`; `cmdb_ci` or `service_tier` or `planned_start`] | `freeze_windows` requires [`name` or `start_time`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `organization_name` | `string` | `"Standard Industry Baseline"` | Organization label stamped into JSON/Markdown reports when bound |

See [`../../README.md`](../../README.md) for the `itsm-command-center` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
