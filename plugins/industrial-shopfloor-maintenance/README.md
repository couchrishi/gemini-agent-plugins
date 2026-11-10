# Industrial Shopfloor Reliability, Quality & EHS Safety (`industrial-shopfloor-maintenance`)

Optimizes critical spare-part safety stocks and reorder points via censored MTBF reliability modeling, builds 80/20 scrap defect Paretos with CapEx payback evaluation, and enforces strict EHS Permit-to-Work LOTO and gas-test safety gates.

## Included Workflow Skills

1. **`asset-reliability-spares-planner`** ([SKILL.md](skills/asset-reliability-spares-planner/SKILL.md)) — Calculates right-censored MTBF, lead-time demand, safety stock, Reorder Point (ROP), and critical stockout expedite POs.
2. **`quality-capex-rca-copilot`** ([SKILL.md](skills/quality-capex-rca-copilot/SKILL.md)) — Builds 80/20 manufacturing scrap cost Paretos, isolates >=2x anomalous supplier lots, and computes CapEx payback hurdles.
3. **`ehs-safety-permit-auditor`** ([SKILL.md](skills/ehs-safety-permit-auditor/SKILL.md)) — Enforces zero-compromise LOTO isolation, confined-space O2 (19.5-23.5%), 0% LEL gas freshness, fire watch, and worker certification checks.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/industrial-shopfloor-maintenance.zip`
- **Granular 1-Hop Upload:** `dist/skills/asset-reliability-spares-planner.zip`, `dist/skills/quality-capex-rca-copilot.zip`, `dist/skills/ehs-safety-permit-auditor.zip`
