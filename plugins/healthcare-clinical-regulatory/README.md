# Healthcare Clinical Trial, Pharmacovigilance & Prior Auth (`healthcare-clinical-regulatory`)

Validates clinical Schedule of Assessments schedules vs endpoints and enrollment capacity, checks E2B ICSR 4 minimum criteria and 7/15-day statutory clocks with PHI redaction alerts, and audits prior authorization packets against payer criteria.

## Included Workflow Skills

1. **`clinical-protocol-feasibility`** ([SKILL.md](skills/clinical-protocol-feasibility/SKILL.md)) — Detects missing endpoint procedures in trial Schedules of Assessments and projects net IRB-approved screen-adjusted enrollment.
2. **`pharmacovigilance-safety-intake`** ([SKILL.md](skills/pharmacovigilance-safety-intake/SKILL.md)) — Validates 4 ICH minimum ICSR criteria, calculates 7-day/15-day/90-day statutory clocks from awareness_date, and traps raw PHI leaks.
3. **`prior-auth-medical-necessity`** ([SKILL.md](skills/prior-auth-medical-necessity/SKILL.md)) — Matches CPT prior-auth packets against covered ICD-10 prefixes, step-therapy trial durations, and required diagnostic labs.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/healthcare-clinical-regulatory.zip`
- **Granular 1-Hop Upload:** `dist/skills/clinical-protocol-feasibility.zip`, `dist/skills/pharmacovigilance-safety-intake.zip`, `dist/skills/prior-auth-medical-necessity.zip`
