# Executive Briefing & Chief of Staff Ops (`executive-briefing-ops`)

Prepares daily executive briefings with calendar conflict and commitment tracking, extracts structured action/decision packs from meeting transcripts, and synthesizes multi-signal stakeholder account dossiers. Pairs live `/work` connectors (`Google Calendar, Gmail, Google Drive, Google Docs, Google Sheets, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams), Salesforce, Slack`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Chief of Staff / Executive Assistant | Preparing a VP or C-suite 06:30 daily readiness brief | [`daily-executive-briefing`](skills/daily-executive-briefing/README.md) | `scripts/agenda_commitment_tracker.py` |
| Program Manager / Scrum Lead | Converting raw executive meeting transcripts into tracked deliverables | [`meeting-to-execution-pack`](skills/meeting-to-execution-pack/README.md) | `scripts/transcript_action_extractor.py` |
| Enterprise Account Executive / VP | Preparing for an imminent renewal or executive sponsor call | [`stakeholder-account-prep`](skills/stakeholder-account-prep/README.md) | `scripts/dossier_synthesizer.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`executive-briefing-ops.zip`](../../dist/bundles/executive-briefing-ops.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/daily-executive-briefing.zip`](../../dist/skills/daily-executive-briefing.zip) — Reconciles calendar events, priority threads, and open action items into time-boxed prep blocks with conflict and overdue alerts.
  - [`dist/skills/meeting-to-execution-pack.zip`](../../dist/skills/meeting-to-execution-pack.zip) — Extracts owner-assigned commitments, decision logs, unresolved blockers, and repeat carryovers from meeting transcripts.
  - [`dist/skills/stakeholder-account-prep.zip`](../../dist/skills/stakeholder-account-prep.zip) — Aggregates account ARR milestones, open escalations, executive touchpoints, and renewal countdowns into scored stakeholder dossiers.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`executive-briefing-ops.zip`](../../dist/bundles/executive-briefing-ops.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/executive-briefing-ops` / `@executive-briefing-ops` so Layer 1 (`remote_cli mcp`) pulls live data from `Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Executive_Briefing_and_Dossiers_Sample.docx` (`4,145 B`, `.docx` document with `8` embedded tables)](../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx):

```bash
python3 plugins/executive-briefing-ops/skills/daily-executive-briefing/scripts/agenda_commitment_tracker.py \
  --input examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx \
  --config plugins/executive-briefing-ops/skills/daily-executive-briefing/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Google Calendar`, `Gmail`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Salesforce`, `Slack`.
- **Connector Fetch Guidance**: Collect day calendar events, Gmail/Outlook threads, Meet transcripts, and Salesforce account snapshots via remote_cli mcp before building overlap checks, action tables, and stakeholder briefs in Python.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Executive_Briefing_and_Dossiers_Sample.docx` (`4,145 B`, `.docx` document with `8` embedded tables)](../../examples/executive-briefing-ops/Apex_Executive_Briefing_and_Dossiers_Sample.docx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`deal-desk-approval-baseline.md`](../../shared/baselines/deal-desk-approval-baseline.md), [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md), [`salesforce-crm-soql-traps.md`](../../shared/traps/salesforce-crm-soql-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Sending executive follow-up emails or stakeholder outreach via Gmail or Outlook; Modifying, rescheduling, or declining multi-attendee Calendar events; Posting meeting action summaries to shared Slack or Microsoft Teams channels.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Untrusted external email/transcript instruction quarantine before action extraction; Strict pagination/truncation propagation preventing silent omission of afternoon events; Time-zone normalization and double-booked conflict interval overlap math.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekday Executive Morning Briefing" on cron `30 6 * * 1-5` (`UTC`) with instruction: "Build the weekday morning executive briefing using scripts/agenda_commitment_tracker.py. Detect overlapping meetings, missing pre-read documents, back-to-back fatigue stretches, and overdue action commitments, and save a private Google Doc brief without sending any external emails.""*

## Example Queries & Verified Outcomes

- **`daily-executive-briefing`** ([skill guide](skills/daily-executive-briefing/README.md)): Connector prompt: *"Prepare my morning executive briefing for 2026-11-10 across Calendar, Gmail, and our Cymbal Financial steering action list."* Verified starter check against `Apex_Executive_Briefing_and_Dossiers_Sample.docx` (`155.8 ms`): `briefing_date=2026-11-11`, `active_meeting_count=3`, `total_booked_minutes=180`, `double_booking_count=1`.
- **`meeting-to-execution-pack`** ([skill guide](skills/meeting-to-execution-pack/README.md)): Connector prompt: *"Convert today's Apex Manufacturing Steering Committee Google Meet transcript into an execution pack and check carryovers against last week's open actions."* Verified starter check against `Apex_Executive_Briefing_and_Dossiers_Sample.docx` (`145.6 ms`): `segment_count=4`, `action_count=2`, `unassigned_action_count=1`, `decision_count=1`.
- **`stakeholder-account-prep`** ([skill guide](skills/stakeholder-account-prep/README.md)): Connector prompt: *"Build an executive sponsor prep brief for Meridian BioPharma ahead of Friday's QBR using Salesforce and our escalation tracker."* Verified starter check against `Apex_Executive_Briefing_and_Dossiers_Sample.docx` (`146.3 ms`): `account_count=3`, `red_account_count=2`, `amber_account_count=0`, `green_account_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-11`** (`26-page Board PDF + live Calendar/Mail/Issue Tracker`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.880 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.880 / 1.000`) and `Prose-Only Baseline` (`PASS 1.000 / 1.000`). Verified domain traps: 30-minute double-booked calendar collision detection; External QBR missing pre-read artifact flag; Multi-surface overdue commitment tracking (EXEC-ACT-01/02).
