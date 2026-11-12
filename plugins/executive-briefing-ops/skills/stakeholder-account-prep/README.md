# Stakeholder Account Prep (`stakeholder-account-prep`)

Aggregates commercial ARR milestones, renewal countdowns, open P1/P2 escalations, and executive touchpoints into scored stakeholder prep dossiers. Deterministic computation executes via [`scripts/dossier_synthesizer.py`](scripts/dossier_synthesizer.py). Domain guards enforced: Emits UNVERIFIED_INSUFFICIENT_SCOPE when CRM or escalation feeds are missing; Computes renewal countdown and touchpoint staleness deterministically. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Enterprise Account Executive / VP**: Triggered when preparing for an imminent renewal or executive sponsor call; scores red/amber account risk using renewal days remaining, open Sev-1s, and touchpoint staleness.
- **Customer Success Director**: Triggered when aligning cross-functional executives before strategic customer reviews; quantifies combined ARR at risk (`$2.27M+`) and highlights overdue sponsor check-ins.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`stakeholder-account-prep.zip`](../../../../dist/skills/stakeholder-account-prep.zip) (or the full department bundle [`executive-briefing-ops.zip`](../../../../dist/bundles/executive-briefing-ops.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx).
4. Ask naturally in chat or invoke directly with `/stakeholder-account-prep` or `@stakeholder-account-prep`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.dossier_synthesizer import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"accounts": [{"account_id": r.get("Source account_id"), "arr_usd": r.get("Source arr_usd")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/executive-briefing-ops/skills/stakeholder-account-prep/scripts/dossier_synthesizer.py \
  --input examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx \
  --config plugins/executive-briefing-ops/skills/stakeholder-account-prep/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `dossier_synthesizer.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack` via `remote_cli mcp`):** "Build an executive sponsor prep brief for Meridian BioPharma ahead of Friday's QBR using Salesforce and our escalation tracker."
2. **Connected Drive / SharePoint Workbooks & Docs:** "CRM connector is down; build the account prep dossier from our Shared Drive Account Health Sheet and flag any missing signal feeds."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx) and ask: "Prepare an executive renewal prep dossier from `Apex_Executive_Briefing_and_Dossiers_Sample.docx`, scoring account health across ARR, days to renewal, open P1/P2 escalations, and executive touchpoint staleness."

## Sample Response

### What You See in Gemini Enterprise Chat

Across `3` strategic accounts in `Apex_Executive_Briefing_and_Dossiers_Sample.docx`, **`2` accounts (`Kestrel Financial` and `Stratos Telecom`) scored `RED`**, placing **`$2,270,000.00` in combined ARR at immediate risk**, while `Meridian Bank` (`$680,000` ARR) sits cleanly at `GREEN` (`92` health).

- **Priority #1 (`Kestrel Financial` — Health `8`, `RED`):** `$1,420,000` ARR renewing in `28` days with `2` open P1s, `4` P2s, `88`-day stale executive touchpoint (`>30d`), and `1` overdue milestone.
- **Priority #2 (`Stratos Telecom` — Health `52`, `RED`):** `$850,000` ARR renewing in `45` days with `1` open P1 and `2` P2 tickets.
- **Approval Confirmation Prompt:** Confirm if you would like to schedule an executive sponsor save call via your connected `Google Calendar` or `Outlook` connector or share the stakeholder prep summary with account leadership via your connected `Slack` or `Teams` connector.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx) (`146.3 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Stakeholder Account Prep Dossier

- **Accounts Analyzed:** 3 (RED: 2, AMBER: 0, GREEN: 1)
- **ARR at Risk (RED+AMBER):** $2,270,000.00

| Account | ARR (USD) | Renewal (d) | P1/P2 | Health | Status | Key Drivers |
| :--- | ---: | ---: | :---: | ---: | :---: | :--- |
| Kestrel Financial | $1,420,000 | 28 | 2/4 | 8 | `RED` | 2 open P1 escalation(s); 4 open P2 ticket(s); Exec touchpoint stale (88d > 30d); Renewal within 28d while elevated risk; 1 overdue milestone(s) |
| Stratos Telecom | $850,000 | 45 | 1/2 | 52 | `RED` | 1 open P1 escalation(s); 2 open P2 ticket(s); Renewal within 45d while elevated risk |
| Meridian Bank | $680,000 | 124 | 0/1 | 92 | `GREEN` | 1 open P2 ticket(s) |
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekday Executive Morning Briefing` routine via `schedule_task`:

```text
Schedule recurring job "Weekday Executive Morning Briefing" on cron `30 6 * * 1-5` (`UTC`) with instruction: "Build the weekday morning executive briefing using scripts/agenda_commitment_tracker.py. Detect overlapping meetings, missing pre-read documents, back-to-back fatigue stretches, and overdue action commitments, and save a private Google Doc brief without sending any external emails."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `accounts`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `accounts` requires [`account_id` or `account_name`; `arr_usd` or `renewal_date` or `nps_score`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `renewal_critical_window_days` | `integer` | `90` | Days to contract renewal below which stakeholder briefs trigger high-urgency renewal flags. |
| `touchpoint_stale_days` | `integer` | `30` | Days since last executive touchpoint before stakeholder cadence is flagged stale. |

See [`../../README.md`](../../README.md) for the `executive-briefing-ops` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
