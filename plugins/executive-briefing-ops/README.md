# Executive Briefing & Chief of Staff Ops (`executive-briefing-ops`)

Automates weekday executive prep briefings, meeting transcript action/decision extraction, and multi-signal stakeholder account dossiers with draft-first safety gates.

## Included Workflow Skills

1. **`daily-executive-briefing`** ([SKILL.md](skills/daily-executive-briefing/SKILL.md)) — Reconciles calendar meetings, priority email threads, and open action trackers (`agenda_commitment_tracker.py`), detecting overlapping invites, missing pre-reads, and overdue deliverables.
2. **`meeting-to-execution-pack`** ([SKILL.md](skills/meeting-to-execution-pack/SKILL.md)) — Parses JSON or text transcripts (`transcript_action_extractor.py`) into owner-assigned commitments, decision logs, unresolved blockers, and repeat carryover counts.
3. **`stakeholder-account-prep`** ([SKILL.md](skills/stakeholder-account-prep/SKILL.md)) — Synthesizes contract ARR, renewal windows, open P1/P2 escalations, touchpoint freshness, and NPS signals (`dossier_synthesizer.py`) into Red/Amber/Green account briefs.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/executive-briefing-ops.zip`
- **Granular 1-Hop Upload:** `dist/skills/daily-executive-briefing.zip`, `dist/skills/meeting-to-execution-pack.zip`, `dist/skills/stakeholder-account-prep.zip`
