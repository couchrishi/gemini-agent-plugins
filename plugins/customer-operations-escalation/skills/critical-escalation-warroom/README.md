# Critical Customer Escalation War-Room (`critical-escalation-warroom`)

Quantifies customer escalation severity and churn exposure (0-100) combining open Sev1/Sev2 backlog, SLA breaches, ARR, renewal proximity, outage hours, and competitor threats. Deterministic computation executes via [`scripts/escalation_exposure_scorer.py`](scripts/escalation_exposure_scorer.py). Domain guards enforced: Weights ARR, renewal proximity <= 90d, Sev1s, and SLA breaches deterministically; Quantifies total arr_at_war_room_risk_usd accurately. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **VP of Customer Support / Escalation Manager**: Triggered when prioritizing multi-customer Sev-1 incidents into daily executive war rooms; scores risk dynamically across ARR (`>=$250k` VIP tier), days to renewal (`<=90d`), and Sev-1 count (`$2.27M` ARR at risk).
- **Technical Account Manager (TAM) Lead**: Triggered when allocating scarce engineering tiger-team hours across competing red accounts; ranks escalation priority deterministically instead of reacting to loudest inbox volume.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`critical-escalation-warroom.zip`](../../../../dist/skills/critical-escalation-warroom.zip) (or the full department bundle [`customer-operations-escalation.zip`](../../../../dist/bundles/customer-operations-escalation.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx).
4. Ask naturally in chat or invoke directly with `/critical-escalation-warroom` or `@critical-escalation-warroom`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_xlsx_workbook
from scripts.escalation_exposure_scorer import analyze, render_markdown

wb = read_xlsx_workbook(Path("customer_export.xlsx"))
print({tab: (list(rows[0].keys()) if rows else []) for tab, rows in wb.items()})

# Shape mismatched customer tabs/columns into a canonical payload dict:
payload = {"escalations": [{"escalation_id": r.get("Custom escalation_id"), "arr_usd": r.get("Custom arr_usd")} for r in wb["Source_Tab"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/customer-operations-escalation/skills/critical-escalation-warroom/scripts/escalation_exposure_scorer.py \
  --input examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx \
  --config plugins/customer-operations-escalation/skills/critical-escalation-warroom/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `escalation_exposure_scorer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Salesforce`, `ServiceNow`, `Google Docs`, `Google Sheets`, `Google Drive`, `Slack` via `remote_cli mcp`):** "Score Stratos Telecom escalation ($650k ARR, renewal in 45 days, 2 Sev1 cases, competitor threat) across CRM and CSM."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Rank accounts in our Drive VIP Escalation Sheet separating WAR_ROOM from HIGH_TOUCH_TAM."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx) and ask: "Prioritize the active customer escalations in `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` by composite ARR exposure, days to renewal, Sev-1 ticket count, SLA breaches, and competitive churn risk for today's executive war room."

## Sample Response

### What You See in Gemini Enterprise Chat

Scoring `3` escalated accounts (`$2,580,000.00` total ARR) in `Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx` **routes `2` accounts totaling `$2,270,000.00` ARR into `WAR_ROOM_SEV0_EXEC`**: **`Kestrel Financial` (`100.0` exposure, `28d` renewal)** and **`Stratos Telecom` (`72.4` exposure, `45d` renewal)**.

- **War-Room Priority #1 (`ESC-APX-901` — `Kestrel Financial`, Score `100.0`):** `$1,420,000.00` ARR renewing in `28d` with `2` active Sev-1s, `3` SLA breaches, `8.5h` 30d downtime, and active competitor evaluation.
- **War-Room Priority #2 (`ESC-APX-902` — `Stratos Telecom`, Score `72.4`):** `$850,000.00` ARR renewing in `45d` with `1` active Sev-1 and `3.2h` downtime; `ESC-APX-903` (`Nordic Logistics`, `$310k`, `20.0`) stays in `STANDARD_QUEUE`.
- **Approval Confirmation Prompt:** Confirm if you would like to trigger formal executive Sev-0 war rooms for `ESC-APX-901` and `ESC-APX-902` via your connected `ServiceNow` or `Slack` escalation connector (gated by `Auto-Guardian`).

### Verified Deterministic Engine Output

Executed directly against [`Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx`](../../../../examples/customer-operations-escalation/Apex_Customer_Escalations_CSAT_and_Trees_Sample.xlsx) (`131.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Critical Customer Escalation War-Room Triage

- **Escalations Scored:** 3 | **War-Room Exec:** 2 | **War-Room ARR at Risk:** $2,270,000.00

| Escalation | Account | ARR | Renewal (d) | Exposure Score | Tier | Primary Drivers |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `ESC-APX-901` | Kestrel Financial | $1,420,000.00 | 28 | **100.0** | `WAR_ROOM_SEV0_EXEC` | 2 active Sev1 tickets (+30), 3 SLA breaches, VIP ARR >= $250,000, Renewal in 28d, 8.5h downtime in 30d, Active competitor evaluation |
| `ESC-APX-902` | Stratos Telecom | $850,000.00 | 45 | **72.4** | `WAR_ROOM_SEV0_EXEC` | 1 active Sev1 tickets (+18), 1 SLA breaches, VIP ARR >= $250,000, Renewal in 45d, 3.2h downtime in 30d |
| `ESC-APX-903` | Nordic Logistics | $310,000.00 | 140 | **20.0** | `STANDARD_QUEUE` | VIP ARR >= $250,000 |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Hourly VIP Escalation Radar` routine via `schedule_task`:

```text
Schedule recurring job "Hourly VIP Escalation Radar" on cron `0 * * * *` (`UTC`) with instruction: "Run the hourly VIP escalation exposure check via scripts/escalation_exposure_scorer.py across open Sev1/Sev2 accounts and renewal windows."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `escalations`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `escalations` requires [`escalation_id` or `account_name`; `arr_usd` or `open_sev1_tickets` or `sla_breached_count`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `war_room_score_threshold` | `number` | `70.0` | Composite score threshold for executive war-room activation. |
| `vip_arr_threshold_usd` | `number` | `250000.0` | ARR floor classifying a customer as VIP strategic tier. |
| `imminent_renewal_days` | `integer` | `90` | Days-to-renewal window amplifying churn exposure. |

See [`../../README.md`](../../README.md) for the `customer-operations-escalation` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
