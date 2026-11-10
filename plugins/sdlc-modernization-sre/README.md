# SDLC Modernization, Security PR & SRE Ops (`sdlc-modernization-sre`)

Supports engineering modernization and reliability teams with legacy code-to-PRD traceability extraction, deterministic SRE postmortem SLO math, and automated PR security/migration gating.

## Included Workflow Skills

1. **`legacy-code-to-prd`** ([SKILL.md](skills/legacy-code-to-prd/SKILL.md)) — Parses legacy code modules (`spec_traceability_matrix.py`) for entrypoints, SQL R/W table couplings, cyclomatic complexity hotspots, and requirement-to-test traceability coverage.
2. **`sre-incident-postmortem`** ([SKILL.md](skills/sre-incident-postmortem/SKILL.md)) — Computes exact TTD/TTM/TTR intervals, 30-day error-budget burn, availability impact, and corrective-action SLA compliance (`slo_timeline_calculator.py`).
3. **`security-pr-readiness-gate`** ([SKILL.md](skills/security-pr-readiness-gate/SKILL.md)) — Scans unified PR diffs and dependency manifests (`diff_risk_inspector.py`) for credential patterns, removed authorization decorators, unindexed DB migrations, and breaking API changes.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/sdlc-modernization-sre.zip`
- **Granular 1-Hop Upload:** `dist/skills/legacy-code-to-prd.zip`, `dist/skills/sre-incident-postmortem.zip`, `dist/skills/security-pr-readiness-gate.zip`
