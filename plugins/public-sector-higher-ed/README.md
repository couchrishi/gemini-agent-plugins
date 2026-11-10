# Public Sector Casework, Grants & Higher-Ed Ops (`public-sector-higher-ed`)

Evaluates citizen benefits/aid eligibility with strict missing-document cure holds (never silent denials) and SSN redaction, scores public procurement tenders after mandatory debarment/COI pass-fail gates, and validates research grant budgets (F&A indirect caps, unallowables, PI effort) plus accreditation evidence freshness.

## Included Workflow Skills

1. **`citizen-case-eligibility-triager`** ([SKILL.md](skills/citizen-case-eligibility-triager/SKILL.md)) — Computes household FPL income eligibility, enforces missing-document cure holds instead of silent denials, and counts PII redactions.
2. **`procurement-tender-evaluator`** ([SKILL.md](skills/procurement-tender-evaluator/SKILL.md)) — Enforces mandatory debarment/COI/tax pass-fail gates first, then computes lowest-compliant commercial normalization and weighted rank.
3. **`grant-accreditation-evidence-pack`** ([SKILL.md](skills/grant-accreditation-evidence-pack/SKILL.md)) — Validates MTDC base vs F&A indirect cost caps, flags unallowable expenses, checks PI 100% effort cap, and checks accreditation freshness.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/public-sector-higher-ed.zip`
- **Granular 1-Hop Upload:** `dist/skills/citizen-case-eligibility-triager.zip`, `dist/skills/procurement-tender-evaluator.zip`, `dist/skills/grant-accreditation-evidence-pack.zip`
