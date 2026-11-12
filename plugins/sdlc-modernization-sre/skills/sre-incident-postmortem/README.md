# SRE Incident Postmortem & SLO Calculator (`sre-incident-postmortem`)

Computes exact TTD, TTM, and TTR incident intervals, 30-day SLO error-budget burn rates, availability impact, and corrective-action SLA status. Deterministic computation executes via [`scripts/slo_timeline_calculator.py`](scripts/slo_timeline_calculator.py). Domain guards enforced: Computes TTD, TTM, TTR, and weighted 30-day SLO burn deterministically; Flags open action items missing due_date as MISSING_DUE_DATE. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Site Reliability Engineer (SRE)**: Triggered when reconciling outage timelines and SLO error-budget consumption after multi-service incidents; merges overlapping alert intervals (`92m -> 65m` union) and prevents superseded action plans (`v1.0` vs `v2.1`) from entering RCAs.
- **Platform Reliability Director**: Triggered when tracking corrective action closure SLAs (`<=14` days) across P0/P1 postmortems; calculates exact remaining monthly `99.9%` availability budget before approving release freezes.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`sre-incident-postmortem.zip`](../../../../dist/skills/sre-incident-postmortem.zip) (or the full department bundle [`sdlc-modernization-sre.zip`](../../../../dist/bundles/sdlc-modernization-sre.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/sre-incident-postmortem` or `@sre-incident-postmortem`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.slo_timeline_calculator import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"incidents": [{"incident_id": r.get("Custom incident_id"), "started_at": r.get("Custom started_at")} for r in wb["Source_Tab"]], "action_items": wb["action_items"]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/sdlc-modernization-sre/skills/sre-incident-postmortem/scripts/slo_timeline_calculator.py \
  --input examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx \
  --config plugins/sdlc-modernization-sre/skills/sre-incident-postmortem/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `slo_timeline_calculator.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`GitHub`, `Jira`, `Confluence`, `BigQuery`, `Google Drive`, `Google Docs`, `Google Sheets`, `Slack` via `remote_cli mcp`):** "Compute 30-day SLO error-budget burn and TTD/TTM/TTR intervals for Stratos Telecom's core auth incidents."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Audit the open corrective actions in our SRE Postmortem Google Doc and flag overdue items."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx) and ask: "Reconcile the overlapping incident outage windows and postmortem action items in `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx` against our 30-day `99.9%` availability SLO, merging simultaneous intervals so error budget isn't double-counted."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `4` `checkout-gateway` incidents in `Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`, union-merged downtime totaled **`144.0` minutes against a `43.2`-minute monthly `99.9%` SLO budget (`333.33%` consumed; `slo_breached: True` at `99.6667%` availability)**, with **`1` overdue corrective action**.

- **Incident Breakdown:** `INC-2026-0891` (`47.0m` burn), `INC-2026-0892` (`45.0m`), `INC-2026-0910` (`27.0m`), and `INC-2026-0911` (`25.0m`) exceeded monthly budget by `100.8` minutes combined.
- **Corrective Action Tracking:** `0` postmortem actions lack due dates, while `1` remediation task is already past its `14`-day closure SLA.
- **Approval Confirmation Prompt:** Confirm if you would like to file escalation tickets for the overdue postmortem action via your connected `Jira` connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx`](../../../../examples/sdlc-modernization-sre/Apex_SDLC_Modernization_SRE_and_PR_Sample.xlsx) (`143.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# SRE Postmortem Timeline & SLO Burn Report

- **SLO Target:** 99.9% (43.2m budget / 30d)
- **Burned:** 144.0m (333.33%) | **Achieved Availability:** 99.6667% (Breached: `True`)
- **Postmortem Actions:** Overdue=1, Missing Due Date=0

| Incident | Service | TTD (m) | TTM (m) | TTR (m) | Burned (m) |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `INC-2026-0891` | checkout-gateway | 6.0 | 41.0 | 69.0 | 47.0 |
| `INC-2026-0892` | checkout-gateway | 2.0 | 43.0 | 56.0 | 45.0 |
| `INC-2026-0910` | checkout-gateway | 2.0 | 25.0 | None | 27.0 |
| `INC-2026-0911` | checkout-gateway | 2.0 | 23.0 | None | 25.0 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly SRE SLO & Postmortem Review` routine via `schedule_task`:

```text
Schedule recurring job "Weekly SRE SLO & Postmortem Review" on cron `0 9 * * 1` (`UTC`) with instruction: "Run the weekly SRE reliability and postmortem action-item SLA audit via scripts/slo_timeline_calculator.py. Compute 30-day error-budget consumption across P1/P2 incidents, report TTD/TTM/TTR trends, and flag overdue postmortem corrective actions without mutating Jira issues autonomously."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `slo_target_pct`, `window_days`, `incidents`, `action_items`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `incidents` requires [`incident_id` or `service`; `started_at` or `detected_at` or `mitigated_at`] | `action_items` requires [`action_id` or `title`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `default_slo_availability_pct` | `number` | `99.9` | Default 30-day availability SLO target percentage. |
| `postmortem_action_sla_days` | `integer` | `14` | Target days for completing P0/P1 postmortem corrective action items. |

See [`../../README.md`](../../README.md) for the `sdlc-modernization-sre` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
