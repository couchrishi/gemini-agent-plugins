# Conversational BI & Variance Analyst (`conversational-bi-analyst`)

Combines pre-execution SQL safety & M:N fanout auditing, exact zero-residual Volume-Mix-Rate KPI bridges, and RAM-based dataset profiling for verified `emit_a2ui` data stories.

## Included Workflow Skills

1. **`schema-grounded-sql-analyst`** ([SKILL.md](skills/schema-grounded-sql-analyst/SKILL.md)) — Validates SQL against schema metadata (`sql_safety_and_fanout_checker.py`) for missing partition filters, M:N join fanout, destructive DDL/DML, and metric denominator mismatches.
2. **`kpi-anomaly-driver-tree`** ([SKILL.md](skills/kpi-anomaly-driver-tree/SKILL.md)) — Computes exact Volume-Mix-Rate bridges and segment z-score anomaly alerts (`mix_rate_volume_bridge.py`).
3. **`executive-data-story-pack`** ([SKILL.md](skills/executive-data-story-pack/SKILL.md)) — Profiles CSV/JSON datasets in Python RAM (`dataset_profiler_guard.py`) for null rates, quantiles, outliers, truncation ceilings, and verified Canvas chart payloads.

## Quickstart

- **1-Click Department Upload:** `dist/bundles/conversational-bi-analyst.zip`
- **Granular 1-Hop Upload:** `dist/skills/schema-grounded-sql-analyst.zip`, `dist/skills/kpi-anomaly-driver-tree.zip`, `dist/skills/executive-data-story-pack.zip`
