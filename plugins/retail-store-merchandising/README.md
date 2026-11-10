# Retail & CPG Store Ops + Merchandising (`retail-store-merchandising`)

Ranks store shrink loss and phantom inventory (zero-scan anomalies) while skipping unpolled POS stores, attributes promotional unit/margin lift net of cannibalization and basket halo, and audits supplier OTIF scorecards, chargebacks, and carrier detention.

## Included Workflow Skills

1. **`store-ops-shrink-copilot`** ([SKILL.md](skills/store-ops-shrink-copilot/SKILL.md)) — Ranks store physical shrink loss $, detects zero-scan phantom inventory cleanly, and prioritizes store floor cycle counts.
2. **`merchandising-assortment-planner`** ([SKILL.md](skills/merchandising-assortment-planner/SKILL.md)) — Normalizes baseline vs promo durations, deducts sibling cannibalization, adds basket halo, and computes net promo margin ROI.
3. **`supplier-otif-chargeback-auditor`** ([SKILL.md](skills/supplier-otif-chargeback-auditor/SKILL.md)) — Scores PO On-Time and In-Full compliance, honors weather/buyer exclusions, and computes vendor chargebacks vs detention fees.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/retail-store-merchandising.zip`
- **Granular 1-Hop Upload:** `dist/skills/store-ops-shrink-copilot.zip`, `dist/skills/merchandising-assortment-planner.zip`, `dist/skills/supplier-otif-chargeback-auditor.zip`
