# Incident Triage & Routing (`incident-triage-routing`)

Triages active ServiceNow and Jira incidents using business-elapsed SLA burn, clusters correlated CI/error storms, and ranks matching runbooks. Deterministic computation executes via [`scripts/sla_cluster_triage.py`](scripts/sla_cluster_triage.py). Domain guards enforced: Normalizes ServiceNow numeric state codes and excludes state=8 canceled rows; Uses business_elapsed_minutes or subtracts sla_paused_minutes instead of raw wall-clock duration. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Major Incident Manager / Duty SRE**: Triggered when triaging active ServiceNow or Jira Service Management Sev-1/2 queues; detects correlated spike clusters (`RB-PAYMENT-POOL`), filters canceled rows, and computes true business SLA burn.
- **IT Service Desk Team Lead**: Triggered when preventing impending P1/P2 contractual SLA breaches across shifts; ranks `AT_RISK` (`>=75%` SLA budget consumed) and breached tickets for targeted reassignment.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`incident-triage-routing.zip`](../../../../dist/skills/incident-triage-routing.zip) (or the full department bundle [`itsm-command-center.zip`](../../../../dist/bundles/itsm-command-center.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/incident-triage-routing` or `@incident-triage-routing`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.sla_cluster_triage import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"incidents": [{"incident_id": r.get("Custom incident_id"), "priority": r.get("Custom priority")} for r in wb["Source_Tab"]], "runbooks": wb["runbooks"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/itsm-command-center/skills/incident-triage-routing/scripts/sla_cluster_triage.py \
  --input examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx \
  --config plugins/itsm-command-center/skills/incident-triage-routing/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `sla_cluster_triage.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`ServiceNow`, `Jira`, `Confluence`, `Google Drive`, `Google Sheets`, `Google Docs`, `Slack` via `remote_cli mcp`):** "Triage Cymbal Financial's active ServiceNow incident queue, excluding canceled tickets and subtracting paused hold time from SLA burn."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Read today's Incident Export Sheet and Runbooks Doc in Shared Drive to rank our top SLA risks."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx) and ask: "Triage the active incident backlog and runbook catalog in the attached `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` workbook, compute business SLA burn, cluster correlated infrastructure spikes, and recommend targeted reassignments without auto-reassigning P1s."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `4` active incidents in `Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx` (`0` closed/canceled excluded), **`0` tickets have breached or hit `AT_RISK` yet**, though **`1` correlated P1 spike cluster (`3` P1 incidents on `checkout-gateway`)** is actively burning SLA up to `68.8%`.

- **Spike Cluster Detected:** `INC-2026-0910` (`68.8%` SLA burn), `INC-2026-0911` (`45.8%`), and `INC-2026-0912` (`31.2%`) all hit `checkout-gateway` and map directly to runbook *Checkout DB & Redis Connection Pool Recovery*.
- **Secondary Queue Item:** `INC-2026-0920` (P2 on `auth-gateway`, `8.3%` SLA burn) maps to *IdP SAML Certificate Rotation*.
- **Approval Confirmation Prompt:** Confirm if you would like to cluster-link and route the `3` P1 `checkout-gateway` tickets via your connected `ServiceNow` or `Jira` connector (gated by `Auto-Guardian` for P1/bulk reassignment).

### Verified Deterministic Engine Output

Executed directly against [`Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx`](../../../../examples/itsm-command-center/Apex_ITSM_Incidents_CAB_and_KCS_Sample.xlsx) (`146.7 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# ITSM Incident Triage & SLA Burn Report

- **Active Backlog:** 4 (Breached: 0, At Risk: 0)
- **Spike Clusters Detected:** 1 | **Canceled Excluded:** 0

| Incident | Priority | State | CI | SLA Burn % | Status | Top Runbook |
| :--- | :---: | :--- | :--- | ---: | :---: | :--- |
| `INC-2026-0910` | P1 | New | checkout-gateway | 68.8% | `ON_TRACK` | Checkout DB & Redis Connection Pool Recovery |
| `INC-2026-0911` | P1 | New | checkout-gateway | 45.8% | `ON_TRACK` | Checkout DB & Redis Connection Pool Recovery |
| `INC-2026-0912` | P1 | In Progress | checkout-gateway | 31.2% | `ON_TRACK` | Checkout DB & Redis Connection Pool Recovery |
| `INC-2026-0920` | P2 | In Progress | auth-gateway | 8.3% | `ON_TRACK` | IdP SAML Certificate Rotation |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly SLA Breach Watch` routine via `schedule_task`:

```text
Schedule recurring job "Hourly SLA Breach Watch" on cron `0 * * * *` (`UTC`) with instruction: "Execute hourly incident triage and SLA breach scan via scripts/sla_cluster_triage.py. Highlight active P1/P2 tickets above 75% business-elapsed SLA budget, flag emerging CI/error spike clusters, and recommend top matching runbooks without mutating ticket assignments automatically."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_time`, `incidents`, `runbooks`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `incidents` requires [`incident_id` or `number`; `priority` or `short_description` or `state`] | `runbooks` requires [`runbook_id` or `title`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `p1_resolution_minutes` | `integer` | `240` | P1 contractual resolution SLA target in minutes (24x7). |
| `p2_resolution_minutes` | `integer` | `480` | P2 contractual resolution SLA target in minutes (24x7). |
| `p3_resolution_minutes` | `integer` | `1440` | P3 contractual resolution SLA target in business minutes (8x5). |
| `p4_resolution_minutes` | `integer` | `2400` | P4 contractual resolution SLA target in business minutes (8x5). |
| `sla_at_risk_pct` | `number` | `75.0` | Percentage of SLA budget consumed at which active incidents flag AT_RISK. |
| `spike_cluster_min` | `integer` | `3` | Minimum correlated open tickets per CI/error signature to declare an incident storm cluster. |

See [`../../README.md`](../../README.md) for the `itsm-command-center` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
