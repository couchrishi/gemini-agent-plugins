# Financial Services Credit, KYB/AML & Claims Underwriting (`fsi-credit-kyc-claims`)

Calculates commercial borrower DSCR, net leverage, and interest coverage under multi-shock stress scenarios, resolves multi-hop UBO beneficial ownership with AML velocity/structuring checks, and evaluates insurance claims deterministically.

## Included Workflow Skills

1. **`commercial-credit-memo-analyst`** ([SKILL.md](skills/commercial-credit-memo-analyst/SKILL.md)) — Calculates DSCR, Net Leverage, Interest Coverage, and Current Ratio across Base, -10%/-20% revenue, and +200bps rate shocks.
2. **`kyc-aml-screening-dossier`** ([SKILL.md](skills/kyc-aml-screening-dossier/SKILL.md)) — Traverses multi-hop holding DAGs to compute cumulative UBO ownership %, enforces 10% EDD drop, and detects velocity/structuring spikes.
3. **`insurance-claims-triage-pack`** ([SKILL.md](skills/insurance-claims-triage-pack/SKILL.md)) — Validates policy effective periods and peril exclusions, computes deductible/coinsurance/sublimit payouts, and flags >$100k reserves.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/fsi-credit-kyc-claims.zip`
- **Granular 1-Hop Upload:** `dist/skills/commercial-credit-memo-analyst.zip`, `dist/skills/kyc-aml-screening-dossier.zip`, `dist/skills/insurance-claims-triage-pack.zip`
