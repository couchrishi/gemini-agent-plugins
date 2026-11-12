# Meeting to Execution Pack (`meeting-to-execution-pack`)

Transforms meeting transcripts and raw notes into owner-assigned commitments, decision logs, unresolved blockers, and repeat carryover trackers. Deterministic computation executes via [`scripts/transcript_action_extractor.py`](scripts/transcript_action_extractor.py). Domain guards enforced: Preserves UNASSIGNED owner instead of hallucinating when transcript lacks attribution; Tracks repeat carryovers across prior open action items. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Program Manager / Scrum Lead**: Triggered when converting raw executive meeting transcripts into tracked deliverables; extracts owners, hard due dates, blockers, and prior-meeting carryover without duplicate tickets.
- **Customer Executive Sponsor**: Triggered when issuing post-QBR recaps to external account stakeholders; splits internal notes from customer-ready follow-ups behind a Gmail/Slack send gate.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`meeting-to-execution-pack.zip`](../../../../dist/skills/meeting-to-execution-pack.zip) (or the full department bundle [`executive-briefing-ops.zip`](../../../../dist/bundles/executive-briefing-ops.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx).
4. Ask naturally in chat or invoke directly with `/meeting-to-execution-pack` or `@meeting-to-execution-pack`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_json_or_jsonl
from scripts.transcript_action_extractor import analyze, render_markdown

raw = Path("customer_input.txt").read_text(encoding="utf-8")
meta_rows = read_json_or_jsonl(Path("customer_metadata.json"))
payload = {"raw_transcript": raw, "segments": [{"text": r["Source text"]} for r in meta_rows]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/executive-briefing-ops/skills/meeting-to-execution-pack/scripts/transcript_action_extractor.py \
  --input examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx \
  --config plugins/executive-briefing-ops/skills/meeting-to-execution-pack/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `transcript_action_extractor.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack` via `remote_cli mcp`):** "Convert today's Apex Manufacturing Steering Committee Google Meet transcript into an execution pack and check carryovers against last week's open actions."
2. **Connected Drive / SharePoint Workbooks & Docs:** "Read Tab 1 and Tab 2 of our Q4 Exec Sync Google Doc notes and draft a follow-up email to attendees."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx) and ask: "Convert the meeting transcript and prior commitments in `Apex_Executive_Briefing_and_Dossiers_Sample.docx` into an execution pack with named owners, due dates, formal decisions, unassigned tasks needing ownership, and carryovers."

## Sample Response

### What You See in Gemini Enterprise Chat

From `4` transcript segments in `Apex_Executive_Briefing_and_Dossiers_Sample.docx`, `2` concrete action items, `1` formal financial hold decision (`DEC-1` by Nadia Patel), and `3` open carryovers from prior meetings were extracted.

- **Accountable Action vs. Unassigned Gap:** `ACT-1` assigns Alex Rivera the Kestrel Financial SSO failover plan due `2026-11-13`, while `ACT-2` (holiday freeze exceptions before Friday CAB) remains `UNASSIGNED` with no due date.
- **Recorded Decision:** `DEC-1` places manual holds on duplicate invoices `INV-APX-US-1915` and `INV-APX-US-1915-DUP` pending VP Finance sign-off.
- **Approval Confirmation Prompt:** Confirm who should own `ACT-2` and approve sending this execution recap to external/internal attendees via your connected `Gmail` or `Outlook` connector or posting to the team channel via your connected `Slack` or `Teams` connector.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Executive_Briefing_and_Dossiers_Sample.docx`](../../../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx) (`145.6 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Execution Pack: Apex Global Q4 Operating & Renewal Sync

- **Actions:** 2 (Unassigned: 1)
- **Decisions:** 1 | **Blockers:** 0 | **Prior Carryovers:** 3

## Owner Commitments

| ID | Owner | Task | Due Hint |
| :--- | :--- | :--- | :--- |
| `ACT-1` | Alex Rivera | I will deliver the Kestrel Financial SSO failover remediation plan by 2026-11-13. | `2026-11-13` |
| `ACT-2` | UNASSIGNED | Someone needs to confirm holiday freeze exceptions before Friday CAB. | `UNSPECIFIED` |

## Decision Log

- `DEC-1` (Nadia Patel): Place manual hold on INV-APX-US-1915 and INV-APX-US-1915-DUP until VP Finance approval.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekday Executive Morning Briefing` routine via `schedule_task`:

```text
Schedule recurring job "Weekday Executive Morning Briefing" on cron `30 6 * * 1-5` (`UTC`) with instruction: "Build the weekday morning executive briefing using scripts/agenda_commitment_tracker.py. Detect overlapping meetings, missing pre-read documents, back-to-back fatigue stretches, and overdue action commitments, and save a private Google Doc brief without sending any external emails."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `meeting_title`, `segments`, `prior_open_commitments`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** top-level `raw_transcript` text | `segments` requires [`text` or `transcript`] | `prior_open_commitments` requires [`id` or `commitment_id` or `task`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `overdue_action_escalation_days` | `integer` | `3` | Days past due before an open commitment is marked escalated. |

See [`../../README.md`](../../README.md) for the `executive-briefing-ops` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
