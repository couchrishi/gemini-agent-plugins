# Conversational BI & Variance Analyst (`conversational-bi-analyst`)

Guards SQL generation against missing partition filters and join fanout explosions, computes exact Volume-Mix-Rate KPI bridges with z-score anomaly detection, and profiles datasets in RAM to emit verified A2UI chart payloads. Pairs live `/work` connectors (`BigQuery, Snowflake, Postgres, Google Sheets, Google Drive, Google Slides`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Analytics Engineer / BI Developer | Validating ad-hoc warehouse queries before running expensive cloud scans | [`schema-grounded-sql-analyst`](skills/schema-grounded-sql-analyst/README.md) | `scripts/sql_safety_and_fanout_checker.py` |
| FP&A / Revenue Analytics Lead | Explaining counter-intuitive executive KPI moves such as blended ARPU jumps | [`kpi-anomaly-driver-tree`](skills/kpi-anomaly-driver-tree/README.md) | `scripts/mix_rate_volume_bridge.py` |
| BI Storytelling / Strategy Lead | Packaging multi-tab analytical exports into board-ready narrative briefs | [`executive-data-story-pack`](skills/executive-data-story-pack/README.md) | `scripts/dataset_profiler_guard.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`conversational-bi-analyst.zip`](../../dist/bundles/conversational-bi-analyst.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/schema-grounded-sql-analyst.zip`](../../dist/skills/schema-grounded-sql-analyst.zip) — Inspects SQL queries and table metadata for missing partition filters, M:N join fanout risks, destructive DDL/DML, and denominator seams.
  - [`dist/skills/kpi-anomaly-driver-tree.zip`](../../dist/skills/kpi-anomaly-driver-tree.zip) — Computes exact zero-residual Volume-Mix-Rate variance decomposition and segment z-score anomaly detection.
  - [`dist/skills/executive-data-story-pack.zip`](../../dist/skills/executive-data-story-pack.zip) — Profiles tabular datasets in RAM for completeness, null rates, quantiles, outliers, truncation ceilings, and A2UI Canvas payloads.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`conversational-bi-analyst.zip`](../../dist/bundles/conversational-bi-analyst.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/conversational-bi-analyst` / `@conversational-bi-analyst` so Layer 1 (`remote_cli mcp`) pulls live data from `BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides` or `Semantic BI Layer / Looker MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` (`4,289 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `KPI_Driver_Segments`, `Data_Metrics_Rows`, `Schema_Table_Registry`)](../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx):

```bash
python3 plugins/conversational-bi-analyst/skills/schema-grounded-sql-analyst/scripts/sql_safety_and_fanout_checker.py \
  --input examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx \
  --config plugins/conversational-bi-analyst/skills/schema-grounded-sql-analyst/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `BigQuery`, `Snowflake`, `Postgres`, `Google Sheets`, `Google Drive`, `Google Slides`.
- **Customer BYO-MCP Servers**: `Semantic BI Layer / Looker MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Fetch dataset metadata, INFORMATION_SCHEMA definitions, dry-run byte estimates, and KPI extract tables from BigQuery, Snowflake, Postgres, or Google Sheets via remote_cli mcp before running Python fanout and mix/rate/volume checks.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` (`4,289 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `KPI_Driver_Segments`, `Data_Metrics_Rows`, `Schema_Table_Registry`)](../../examples/conversational-bi-analyst/Apex_BI_SQL_Funnel_and_Story_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`finance-materiality-baseline.md`](../../shared/baselines/finance-materiality-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`bigquery-sap-erp-traps.md`](../../shared/traps/bigquery-sap-erp-traps.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Executing DDL/DML statements or unpartitioned warehouse queries exceeding max_query_scan_gb; Sharing executive KPI briefings or Slides decks to external leadership distribution lists.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: SQL AST DDL/DML block, missing partition filter flag, and 1:N join fanout double-count guard; Volume + Mix + Rate additive bridge identity check with min_sample_size_guard warnings; Strict BigQuery/Sheets UNFORMATTED_VALUE coercion without string display rounding.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Daily KPI Anomaly Digest" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Run the daily KPI variance and z-score anomaly check using scripts/mix_rate_volume_bridge.py. Decompose revenue/margin changes into exact Volume, Mix, and Rate effects, flag segments exceeding zscore_anomaly_threshold, and save an internal Canvas digest without emailing distribution lists.""*

## Example Queries & Verified Outcomes

- **`schema-grounded-sql-analyst`** ([skill guide](skills/schema-grounded-sql-analyst/README.md)): Connector prompt: *"Check this BigQuery SQL joining `purchase_orders` to `goods_receipts` on `po_id` alone without filtering `posting_date`."* Verified starter check against `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` (`149.4 ms`): `is_read_only_safe=True`, `destructive_keywords=[]`, `referenced_tables=['order_items', 'orders']`, `missing_partition_filter_count=2`.
- **`kpi-anomaly-driver-tree`** ([skill guide](skills/kpi-anomaly-driver-tree/README.md)): Connector prompt: *"Explain Veloce SuperApp's Q3-to-Q4 net revenue change across Ride, Food, and Mart segments from BigQuery."* Verified starter check against `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` (`178.2 ms`): `segment_count=3`, `prior_total_revenue=1360000.0`, `current_total_revenue=2236000.0`, `total_delta=876000.0`.
- **`executive-data-story-pack`** ([skill guide](skills/executive-data-story-pack/README.md)): Connector prompt: *"Profile our Q4 regional orders export from BigQuery and generate a Canvas chart summarizing revenue by region."* Verified starter check against `Apex_BI_SQL_Funnel_and_Story_Sample.xlsx` (`146.3 ms`): `title=Apex Global Q3 ARPU Mix Paradox & Funnel Audit`, `row_count=5`, `column_count=7`, `truncated=False`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-04`** (`5 tabs, 4,505 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.893 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.985 / 1.000`) and `Prose-Only Baseline` (`PASS 0.981 / 1.000`). Verified domain traps: Simpson's paradox blended ARPU increase while all 3 segments fell; Zero-residual Volume/Mix/Rate driver decomposition; 1:N orders->order_items join on customer_id fanout inflation; 420 GB missing partition predicate on order_date.
