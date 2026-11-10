# Finance Variance, 3-Way Match & AR Reconciliation

Controller-grade finance operations bundle covering **AP 3-Way Matching**, **P&L Budget Variance Bridging**, and **AR Aging & Collections Audits** with zero LLM arithmetic guessing and mandatory ERP traps baked in.

## Included Skills

1. **AP Three-Way Match (`ap-three-way-match`)** — Matches PO, Goods Receipt, and Vendor Invoice records in RAM via `reconcile_3way.py`, normalizing SAP `TCURR`/`TCURX` zero/three-decimal currency scales, `SHKZG` credit signs, exact & fuzzy duplicate invoices, and bank-change fraud alerts.
2. **P&L Budget Variance Bridge (`pnl-budget-variance-bridge`)** — Reconciles hierarchical GL accounts via `pnl_variance_engine.py`, verifying parent-to-leaf tie-outs before decomposing Actual vs Budget/Forecast variance into constant-currency volume/rate vs FX translation impact.
3. **AR Aging & Collections Audit (`ar-aging-collections-audit`)** — Classifies customer open balances into `Current`, `1-30`, `31-60`, `61-90`, and `90+` buckets via `aging_bucket_auditor.py`, isolating unapplied credit memos so negative rows never mask `90+` delinquency.

## Safeguards & Starter Baseline

- Evaluated against `shared/baselines/finance-materiality-baseline.md` when `org_configured` is `false`.
- All ERP invoice postings, vendor bank master changes, and external AR dunning notices are HITL-gated via `.gemini-plugin/policy.cel`.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/finance-variance-recon.zip`
- **Granular 1-Hop Upload:** `dist/skills/ap-three-way-match.zip`, `dist/skills/pnl-budget-variance-bridge.zip`, `dist/skills/ar-aging-collections-audit.zip`
