---
name: meeting-to-execution-pack
description: "Transforms meeting transcripts and raw notes into owner-assigned commitments, decision logs, unresolved blockers, and repeat carryover trackers. Use when turning Meet/Teams transcripts into execution packs. Don't use for building morning calendar prep briefs (use daily-executive-briefing)."
created_by: gemini-agent-plugins
---

# Meeting to Execution Pack

## Domain Context & Objective

Extracts owner-assigned commitments, decision logs, unresolved blockers, and repeat carryovers from meeting transcripts. Extracts owner-assigned commitments, decisions, blockers, and carryovers from meeting transcripts. Execute calculations via `scripts/transcript_action_extractor.py` inside persistent `pyrepl` RAM rather than estimating metrics in prompt tokens.

Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Step 1 — Fetch Data via Live `/work` Connectors (Primary) or Attached Files (Fallback)

Query live authorized connectors first before falling back to chat-attached snapshots:

- **Built-in Managed 1P Connectors:** `Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack`.
- **Connector Tool Discovery:** Probe enabled 1P/MCP servers via `remote_cli mcp <connector> list-tools` before running Python engines.
- **Connector Fetch Guidance:** Collect day calendar events, Gmail/Outlook threads, Meet transcripts, and Salesforce account snapshots via remote_cli mcp before building overlap checks, action tables, and stakeholder briefs in Python.
- **Workspace & Attached File Fallback:** When pulling files from Google Docs (`includeTabsContent=true`), Google Sheets (`UNFORMATTED_VALUE`), Shared Drives (`supportsAllDrives=true`), or SharePoint/OneDrive (`@odata.nextLink`), or when the user attaches `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, or `.jsonl` files directly in chat, inspect/stage paths with `view_file` and parse via `scripts/enterprise_io.py`.

## Step 2 — Inspect & Shape Custom Customer Fields in `pyrepl`

Customer exports and live connector responses often use custom tab names or column headers. Inspect real data shape directly in `pyrepl` via `scripts/enterprise_io.py` before computing:

- **Canonical `payload` Shape:** top-level `raw_transcript` text | `segments` requires [`text` or `transcript`] | `prior_open_commitments` requires [`id` or `commitment_id` or `task`] (matching top-level keys under `Expected Inputs` below).
- **Inspect Source Shape Directly in Python:** Call `read_xlsx_workbook(path)` (for `.xlsx`), `read_docx(path)` (for `.docx`), `read_csv_tsv(path)` (for `.csv`/`.tsv`), or `read_json_or_jsonl(path)` (for `.json`/`.jsonl`) in `pyrepl` — or inspect connector JSON keys directly — to see exact tab names, headers, and sample rows first.
- **Normalize Mismatched Fields in 5-10 Lines of Python:** Pass standard exports directly to `analyze(path_or_dict, config=cfg_path)`. When customer tab names, column headers, or nested objects differ, reshape rows into a canonical `payload` dict in a few lines of Python (calling `ask_question` only when two customer columns remain genuinely ambiguous).

## Step 3 — Run Deterministic Python Engine in `pyrepl` (or CLI) with Org Baseline Rules

1. Read `references/config.json` using `view_file` before scoring.
2. When `org_configured` is `false`, apply the bundled starter rubrics (`references/baselines/deal-desk-approval-baseline.md`, `references/baselines/itsm-sla-severity-baseline.md`) and stamp the top of every deliverable verbatim with:
   `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`

| Config Key | Type / Bounds | Default | Operational Role |
| :--- | :--- | :--- | :--- |
| `min_prep_buffer_minutes` | integer, 0..60 | `15` | Minimum gap in minutes expected between external/executive meetings. |
| `overdue_action_escalation_days` | integer, 1..90 | `3` | Days past due before an open commitment is marked escalated. |
| `renewal_critical_window_days` | integer, 14..365 | `90` | Days to contract renewal below which stakeholder briefs trigger high-urgency renewal flags. |
| `touchpoint_stale_days` | integer, 7..180 | `30` | Days since last executive touchpoint before stakeholder cadence is flagged stale. |

Execute `scripts/transcript_action_extractor.py` inside persistent `pyrepl` RAM (resolving `SKILL_DIR` dynamically for single-skill or bundle deployments) or invoke Python CLI fallback:

```python
import sys
from pathlib import Path

SKILL_DIR = next(
    (
        p
        for p in (
            Path("skills/meeting-to-execution-pack"),
            Path("skills/user-skills/meeting-to-execution-pack"),
            Path("skills/executive-briefing-ops"),
            Path("skills/user-skills/executive-briefing-ops"),
            Path("."),
        )
        if (p / "scripts/transcript_action_extractor.py").is_file()
    ),
    next((p.parent.parent for p in Path("skills").rglob("scripts/transcript_action_extractor.py")), Path(".")),
)
sys.modules.pop("scripts", None)
sys.path.insert(0, str(SKILL_DIR))
from scripts.enterprise_io import read_xlsx_workbook, read_docx, read_csv_tsv, read_json_or_jsonl
from scripts.transcript_action_extractor import analyze, render_markdown

cfg_path = SKILL_DIR / "references" / "config.json"

# 1. Pass raw .diff/.sql/.txt/.json paths directly when format already matches:
# payload = source_path_or_dict
# 2. Or build a normalized payload dict from connector output or custom exports in pyrepl:
# payload = {"raw_transcript": text_str, "segments": [{"text": r.get("Source text")} for r in rows]}
result = analyze(
    payload,
    config=cfg_path,
)
print(render_markdown(result))
```

CLI fallback (`python3` from `/workspace` or skill root):

```bash
SKILL_DIR="."
for d in skills/meeting-to-execution-pack skills/user-skills/meeting-to-execution-pack skills/executive-briefing-ops skills/user-skills/executive-briefing-ops skills/*; do
  [ -f "$d/scripts/transcript_action_extractor.py" ] && SKILL_DIR="$d" && break
done
python3 "$SKILL_DIR/scripts/transcript_action_extractor.py" --input payload.json --config "$SKILL_DIR/references/config.json" --format markdown
# Inspect full flags: python3 "$SKILL_DIR/scripts/transcript_action_extractor.py" --help
```
## Input/Output Schema & Enterprise Trap Assertions

| Contract | Keys & Invariants |
| :--- | :--- |
| **Expected Inputs** | `meeting_title`, `segments`, `prior_open_commitments`; optional `metadata` (`truncated`, `done`, `total_available`) |
| **Deterministic Outputs** | `skill`, `baseline_mode`, `baseline_banner`, `meeting_title`, `summary`, `actions`, `decisions`, `blockers`, `carryovers`, `truncation_warnings`; `summary` (`segment_count`, `action_count`, `unassigned_action_count`, `decision_count`, `blocker_count`, `prior_carryover_count`) |
| **Eval & Safety Checks** | Preserves UNASSIGNED owner instead of hallucinating when transcript lacks attribution.; Tracks repeat carryovers across prior open action items. |

Bundled trap guides to enforce: `references/traps/absent-is-not-zero.md`, `references/traps/google-workspace-traps.md`, `references/traps/salesforce-crm-soql-traps.md`, `references/traps/untrusted-content-and-pii.md`.

- Apply `references/traps/absent-is-not-zero.md`, `references/traps/google-workspace-traps.md`, `references/traps/salesforce-crm-soql-traps.md`, and `references/traps/untrusted-content-and-pii.md`.
- Flag `UNASSIGNED` actions and unattributed transcripts explicitly instead of guessing ownership.
- Creating private Doc summaries or email drafts is auto-allowed; emailing external attendees or posting to shared Slack/Chat channels requires explicit user confirmation (HITL).

## Step 4 — Write-Back Governance (`Auto-Guardian`) & Conversational Scheduling (`schedule_task`)

- **Interactive Canvas & Local Drafts (`emit_a2ui`, `write_to_file`):** Project `summary` KPIs (`segment_count`, `action_count`, `unassigned_action_count`, `decision_count`, `blocker_count`, `prior_carryover_count`) as structured Canvas cards and save local Markdown/JSON drafts with `write_to_file` without modifying external systems.
- **Agent Gateway (`Auto-Guardian`) & Explicit User Confirmation:** Any external connector write-back is protected at runtime by `/work`'s Agent Gateway (`Auto-Guardian`) and requires explicit user confirmation prior to execution:
  - Sending executive follow-up emails or stakeholder outreach via Gmail or Outlook
  - Modifying, rescheduling, or declining multi-attendee Calendar events
  - Posting meeting action summaries to shared Slack or Microsoft Teams channels
- **Code-Enforced Python Invariants (`scripts/*.py`):**
  - Untrusted external email/transcript instruction quarantine before action extraction
  - Strict pagination/truncation propagation preventing silent omission of afternoon events
  - Time-zone normalization and double-booked conflict interval overlap math
- **Conversational Scheduling (`schedule_task`):** Only when requested by the user, schedule recurring execution via `schedule_task(title="Weekday Executive Morning Briefing", cron_expression="30 6 * * 1-5", time_zone="UTC", instruction="Build the weekday morning executive briefing using scripts/agenda_commitment_tracker.py. Detect overlapping meetings, missing pre-read documents, back-to-back fatigue stretches, and overdue action commitments, and save a private Google Doc brief without sending any external emails.")`.
