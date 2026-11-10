# Marketplace, Ride-Hailing & SuperApp Ops (`marketplace-superapp-ops`)

Screens merchant catalog listings for prohibited terms, prompt-injection payloads, and price outliers, attributes on-demand delivery SLA breaches across merchant prep vs courier transit with force-majeure waivers, and reconciles merchant GMV, commission fees, FX, and PSP settlements.

## Included Workflow Skills

1. **`merchant-catalog-trust-gate`** ([SKILL.md](skills/merchant-catalog-trust-gate/SKILL.md)) — Detects indirect prompt injection in merchant copy, screens counterfeit/prohibited goods, flags price outliers, and checks attributes.
2. **`logistics-sla-dispute-resolver`** ([SKILL.md](skills/logistics-sla-dispute-resolver/SKILL.md)) — Splits order delays into merchant prep vs courier transit faults, waives verified weather delays, and assigns refund liability.
3. **`commission-payout-reconciler`** ([SKILL.md](skills/commission-payout-reconciler/SKILL.md)) — Reconciles gross GMV, commission take-rates, promo splits, FX conversions, and PSP wires while flagging negative clawbacks.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/marketplace-superapp-ops.zip`
- **Granular 1-Hop Upload:** `dist/skills/merchant-catalog-trust-gate.zip`, `dist/skills/logistics-sla-dispute-resolver.zip`, `dist/skills/commission-payout-reconciler.zip`
