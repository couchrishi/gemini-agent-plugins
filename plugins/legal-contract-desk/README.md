# Legal Contract Desk & Regulatory Compliance (`legal-contract-desk`)

Equips corporate legal and compliance teams with deterministic 1/3/9 contract redline scoring, exact opt-out deadline calendars, and regulatory-to-control coverage audits.

## Included Workflow Skills

1. **`contract-playbook-redliner`** ([SKILL.md](skills/contract-playbook-redliner/SKILL.md)) — Evaluates LoL caps, super-caps, auto-renewal notice windows, governing law, IP/AI training rights, and DPA breach SLAs on a `1/3/9` risk matrix (`clause_risk_matrix.py`).
2. **`executed-obligation-extractor`** ([SKILL.md](skills/executed-obligation-extractor/SKILL.md)) — Computes exact opt-out deadlines (`renewal_date - notice_days`), CPI cap breaches, and recurring audit obligations (`obligation_calendar_builder.py`).
3. **`regulatory-change-mapper`** ([SKILL.md](skills/regulatory-change-mapper/SKILL.md)) — Maps statutory articles against internal controls (`control_gap_mapper.py`), catching uncovered obligations and stale test evidence.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/legal-contract-desk.zip`
- **Granular 1-Hop Upload:** `dist/skills/contract-playbook-redliner.zip`, `dist/skills/executed-obligation-extractor.zip`, `dist/skills/regulatory-change-mapper.zip`
