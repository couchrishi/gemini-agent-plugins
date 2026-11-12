# Employee Onboarding 30/60/90 Navigator (`employee-onboarding-navigator`)

Builds 30/60/90-day onboarding checklists and identifies overdue provisioning, missing Day-1 gates, and blocked task dependencies. Deterministic computation executes via [`scripts/onboarding_plan_builder.py`](scripts/onboarding_plan_builder.py). Domain guards enforced: Flags missing mandatory Day-1 gates explicitly; Detects overdue items relative to start_date + due_day_offset. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **People Ops Onboarding Specialist**: Triggered when tracking Day-1 readiness across IT provisioning, security training, and manager tasks; flags stalled hires, overdue mandatory Day-1 access steps, and missing compliance orientations.
- **IT Workforce Provisioning Lead**: Triggered when auditing cross-system laptop, SSO, and background-clearance blockers prior to start dates; consolidates overdue onboarding owners for batched follow-up reminders.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`employee-onboarding-navigator.zip`](../../../../dist/skills/employee-onboarding-navigator.zip) (or the full department bundle [`people-ops-talent-hub.zip`](../../../../dist/bundles/people-ops-talent-hub.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & ATS Scorecard MCP server`)) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/employee-onboarding-navigator` or `@employee-onboarding-navigator`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.onboarding_plan_builder import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"hires": [{"employee_id": r.get("Custom employee_id"), "start_date": r.get("Custom start_date")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/people-ops-talent-hub/skills/employee-onboarding-navigator/scripts/onboarding_plan_builder.py \
  --input examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx \
  --config plugins/people-ops-talent-hub/skills/employee-onboarding-navigator/references/config.json \
  --format markdown
```

Optional CLI overrides supported by `onboarding_plan_builder.py`: `--as-of`, plus `--sheet` for targeting a specific Excel worksheet.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`, `ServiceNow`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` + Customer BYO-MCP (`Workday HRIS & ATS Scorecard MCP server`) via `remote_cli mcp`):** "Check upcoming Stratos Telecom hires in Workday/ServiceNow HRSD for missing laptop or SSO gates."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit our Drive Onboarding Sheet for hires > 30 days past start with incomplete compliance tasks."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx) and ask: "Review the new-hire onboarding checklist in `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` as of `2026-11-10` to identify stalled hires, overdue tasks, and missing Day-1 IT SSO, laptop shipment, or security policy gates."

## Sample Response

### What You See in Gemini Enterprise Chat

Tracking `2` upcoming/recent hires in `Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx` as of `2026-11-10` shows **both hires (`2 / 2`) in `AT_RISK_MISSING_DAY1_GATES`** across `identity_sso_provisioning`, `laptop_hardware_shipment`, and `security_policy_ack`, including `1` overdue task.

- **Overdue & Stalled (`HIRE-APX-901` — `Taylor Kim`, Cloud Engineering):** Started `2026-11-01` at `50.0%` completion with `1` overdue task and `3` unverified Day-1 IT/security gates.
- **Day-1 Unready (`HIRE-APX-902` — `Devon Brooks`, Global Sales):** Started `2026-11-09` at `0.0%` completion across all `3` mandatory Day-1 gates.
- **Approval Confirmation Prompt:** Confirm if you would like to route onboarding remediation actions or worker status updates via your connected Workday HRIS MCP server or HR ticketing after IT SSO confirmation.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx`](../../../../examples/people-ops-talent-hub/Apex_Workforce_Hiring_and_Onboarding_Sample.xlsx) (`144.4 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# 30/60/90 Employee Onboarding Readiness Tracker (As Of 2026-11-10)

- **Hires Tracked:** 2 | **Stalled/At-Risk:** 2 | **Total Overdue Tasks:** 1 | **Missing Day-1 Gates:** 2

| Hire | Dept | Start Date | Completion | Overdue | Missing Gates | Health |
| :--- | :--- | :--- | ---: | ---: | :--- | :--- |
| `HIRE-APX-901` Taylor Kim | Cloud Engineering | 2026-11-01 | 50.0% | 1 | identity_sso_provisioning, laptop_hardware_shipment, security_policy_ack | `AT_RISK_MISSING_DAY1_GATES` |
| `HIRE-APX-902` Devon Brooks | Global Sales | 2026-11-09 | 0.0% | 0 | identity_sso_provisioning, laptop_hardware_shipment, security_policy_ack | `AT_RISK_MISSING_DAY1_GATES` |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Onboarding Stall Watch` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Onboarding Stall Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly onboarding gate check via scripts/onboarding_plan_builder.py to detect missing Day-1 IT/security gates and stalled 30/60/90 milestones."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `hires`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `hires` requires [`employee_id` or `employee_name`; `start_date` or `tasks` or `task_id`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `organization_name` | `string` | `"Standard Industry Baseline"` | Organization label stamped into JSON/Markdown reports when bound |

See [`../../README.md`](../../README.md) for the `people-ops-talent-hub` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
