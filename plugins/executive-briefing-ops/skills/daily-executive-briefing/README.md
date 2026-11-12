# Daily Executive Briefing (`daily-executive-briefing`)

Builds daily executive briefings reconciling calendar agendas, priority email threads, and open action trackers with conflict and missing pre-read alerts. Deterministic computation executes via [`scripts/agenda_commitment_tracker.py`](scripts/agenda_commitment_tracker.py). Domain guards enforced: Detects exact meeting overlaps excluding declined invitations; Quarantines indirect prompt injections in external email snippets. Direct local uploads support `.xlsx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Chief of Staff / Executive Assistant**: Triggered when preparing a VP or C-suite 06:30 daily readiness brief; flags double-booked calendar overlaps, `<15m` prep buffers, and missing external QBR pre-reads.
- **Business Operations Lead**: Triggered when triaging overnight high-priority emails and escalated commitments; routes overdue action items (`EXEC-ACT-*`) to accountable owners prior to morning standup.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`daily-executive-briefing.zip`](../../../../dist/skills/daily-executive-briefing.zip) (or the full department bundle [`executive-briefing-ops.zip`](../../../../dist/bundles/executive-briefing-ops.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx).
4. Ask naturally in chat or invoke directly with `/daily-executive-briefing` or `@daily-executive-briefing`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.agenda_commitment_tracker import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"events": [{"event_id": r.get("Source event_id")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/executive-briefing-ops/skills/daily-executive-briefing/scripts/agenda_commitment_tracker.py \
  --input examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx \
  --config plugins/executive-briefing-ops/skills/daily-executive-briefing/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `agenda_commitment_tracker.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack` via `remote_cli mcp`):** "Prepare my morning executive briefing for 2026-11-10 across Calendar, Gmail, and our Cymbal Financial steering action list."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Using today's Workspace Calendar export and Gmail urgent threads, generate the briefing and draft replies to priority emails."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx) and ask: "Using the attached `Apex_Executive_Briefing_and_Dossiers_Sample.docx` packet, prepare a `2026-11-11` executive morning briefing highlighting calendar overlaps, missing pre-reads, and overdue action commitments requiring immediate follow-up."

## Sample Response

### What You See in Gemini Enterprise Chat

For `2026-11-11` across `Apex_Executive_Briefing_and_Dossiers_Sample.docx`, your schedule covers `3` active meetings (`180` booked minutes) with `1` 30-minute double-booking between `Apex Global Q3 Close & CFO Audit Committee` and `Kestrel Financial QBR`, `1` missing pre-read, and `2` overdue executive commitments.

- **Calendar Collision & Prep Gaps:** `Apex Global Q3 Close` overlaps `Kestrel Financial QBR` by `30` minutes, and `1` executive session still lacks a linked pre-read (`missing_preread_count = 1`).
- **Overdue Commitments:** `ACT-1` (Nadia Patel, SAP `TCURX` JPY & duplicate AP invoice audit, overdue `6d`) and `ACT-2` (Alex Rivera, Kestrel SSO failover remediation, overdue `3d`) require morning escalation.
- **Approval Confirmation Prompt:** Confirm if you would like to decline/reschedule the conflicting calendar slot via your connected `Google Calendar` or `Outlook` connector or send reminder notes to Nadia Patel and Alex Rivera via your connected `Gmail` or `Outlook` connector.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx) (`155.8 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Daily Executive Briefing (2026-11-11)

- **Meetings:** 3 (180 mins total)
- **Double-Bookings:** 1 | **Missing Pre-Reads:** 1
- **Overdue Commitments:** 2 | **Urgent Threads:** 0

## Calendar Conflicts

- `Apex Global Q3 Close & CFO Audit Committee` overlaps `Kestrel Financial QBR - Executive Renewal Review` by **30 min**

## Overdue Commitments

- `ACT-1` (Nadia Patel): Complete SAP TCURX JPY & duplicate AP invoice audit (Due `2026-11-05`, Overdue `6`d)
- `ACT-2` (Alex Rivera): Deliver Kestrel Financial SSO failover remediation milestone (Due `2026-11-08`, Overdue `3`d)
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekday Executive Morning Briefing` routine via `schedule_task`:

```text
Schedule recurring job "Weekday Executive Morning Briefing" on cron `30 6 * * 1-5` (`UTC`) with instruction: "Build the weekday morning executive briefing using scripts/agenda_commitment_tracker.py. Detect overlapping meetings, missing pre-read documents, back-to-back fatigue stretches, and overdue action commitments, and save a private Google Doc brief without sending any external emails."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `briefing_date`, `events`, `priority_threads`, `commitments`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `events` requires [`event_id` or `title`] | `priority_threads` requires [`thread_id` or `subject`] | `commitments` requires [`id` or `commitment_id` or `task` or `owner`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `min_prep_buffer_minutes` | `integer` | `15` | Minimum gap in minutes expected between external/executive meetings. |
| `overdue_action_escalation_days` | `integer` | `3` | Days past due before an open commitment is marked escalated. |

See [`../../README.md`](../../README.md) for the `executive-briefing-ops` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
