# ERP Procure-to-Pay, GR/IR Clearing & Tariff Cost Engine (`erp-procure-to-pay`)

Reconciles SAP GR/IR clearing imbalances across goods receipts and invoice postings with TCURX scaling, simulates multi-supplier RFx total landed cost under tariff shocks, and rolls up multi-level BOM purchase price variances with cycle detection.

## Included Workflow Skills

1. **`gr-ir-clearing-orchestrator`** ([SKILL.md](skills/gr-ir-clearing-orchestrator/SKILL.md)) — Reconciles SAP WE goods receipts and RE invoice postings with TCURX currency scaling, SHKZG sign flips, and >60d aging classification.
2. **`supplier-rfx-tariff-modeler`** ([SKILL.md](skills/supplier-rfx-tariff-modeler/SKILL.md)) — Simulates multi-supplier RFx bids across FOB, freight, tariffs, shock scenarios, payment financing, and quality defect penalties.
3. **`bom-cost-rollup-variance`** ([SKILL.md](skills/bom-cost-rollup-variance/SKILL.md)) — Explodes multi-level BOMs with scrap factors, guards against circular BOM graphs, and rolls up leaf PPV drivers.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/erp-procure-to-pay.zip`
- **Granular 1-Hop Upload:** `dist/skills/gr-ir-clearing-orchestrator.zip`, `dist/skills/supplier-rfx-tariff-modeler.zip`, `dist/skills/bom-cost-rollup-variance.zip`
