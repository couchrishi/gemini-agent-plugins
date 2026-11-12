# Retail & CPG Store Ops + Merchandising (`retail-store-merchandising`)

Ranks store shrink loss and phantom inventory (zero-scan anomalies) while skipping unpolled POS stores, attributes promotional unit/margin lift net of cannibalization and basket halo, and audits supplier OTIF scorecards, chargebacks, and carrier detention. Pairs live `/work` connectors (`BigQuery, Snowflake, Google Drive, Google Sheets, Google Docs`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Regional Loss Prevention & Inventory Lead | Investigating suspected store shrink vs reporting outages across multi-store POS feeds | [`store-ops-shrink-copilot`](skills/store-ops-shrink-copilot/README.md) | `scripts/store_shrink_task_ranker.py` |
| Category Merchandising Manager | Evaluating seasonal promotional lift, halo margin, and markdown plans | [`merchandising-assortment-planner`](skills/merchandising-assortment-planner/README.md) | `scripts/promo_lift_analyzer.py` |
| Retail Supply Chain Vendor Compliance Lead | Calculating quarterly vendor On-Time In-Full (OTIF) scorecards and deduction claims | [`supplier-otif-chargeback-auditor`](skills/supplier-otif-chargeback-auditor/README.md) | `scripts/otif_detention_calculator.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`retail-store-merchandising.zip`](../../dist/bundles/retail-store-merchandising.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/store-ops-shrink-copilot.zip`](../../dist/skills/store-ops-shrink-copilot.zip) — Ranks store physical shrink loss $, detects zero-scan phantom inventory cleanly, and prioritizes store floor cycle counts.
  - [`dist/skills/merchandising-assortment-planner.zip`](../../dist/skills/merchandising-assortment-planner.zip) — Normalizes baseline vs promo durations, deducts sibling cannibalization, adds basket halo, and computes net promo margin ROI.
  - [`dist/skills/supplier-otif-chargeback-auditor.zip`](../../dist/skills/supplier-otif-chargeback-auditor.zip) — Scores PO On-Time and In-Full compliance, honors weather/buyer exclusions, and computes vendor chargebacks vs detention fees.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`retail-store-merchandising.zip`](../../dist/bundles/retail-store-merchandising.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/retail-store-merchandising` / `@retail-store-merchandising` so Layer 1 (`remote_cli mcp`) pulls live data from `BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs` or `SAP Retail ERP & POS Store Telemetry MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` (`3,982 B`, `.xlsx` workbook with tabs: `Store_SKU_Shrink_Ledger`, `Promo_Campaign_Lift`, `Supplier_OTIF_Deliveries`)](../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx):

```bash
python3 plugins/retail-store-merchandising/skills/store-ops-shrink-copilot/scripts/store_shrink_task_ranker.py \
  --input examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx \
  --config plugins/retail-store-merchandising/skills/store-ops-shrink-copilot/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `BigQuery`, `Snowflake`, `Google Drive`, `Google Sheets`, `Google Docs`.
- **Customer BYO-MCP Servers**: `SAP Retail ERP & POS Store Telemetry MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Pull store perpetual inventory, POS terminal polling health, promo elasticity tables, and ASN/POD Dock timestamps from BigQuery/Snowflake or customer SAP Retail / POS MCP servers via remote_cli mcp before Python shrink and OTIF math.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` (`3,982 B`, `.xlsx` workbook with tabs: `Store_SKU_Shrink_Ledger`, `Promo_Campaign_Lift`, `Supplier_OTIF_Deliveries`)](../../examples/retail-store-merchandising/Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`finance-materiality-baseline.md`](../../shared/baselines/finance-materiality-baseline.md), [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`bigquery-sap-erp-traps.md`](../../shared/traps/bigquery-sap-erp-traps.md), [`sharepoint-onedrive-kql-traps.md`](../../shared/traps/sharepoint-onedrive-kql-traps.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Posting perpetual inventory shrink write-offs impacting store COGS via SAP Retail MCP; Issuing supplier OTIF chargeback or detention debit memos via ERP AP MCP.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Mandatory exclusion of unpolled POS stores (pos_poll_status == MISSING) before shrink/write-off attribution; Baseline-adjusted promo net margin ROI guard preventing margin-destructive promotions from passing on gross unit lift; Strict contractual OTIF window and dock-wait grace-minute detention math.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Daily Store Shrink & Zero-Scan Watch" on cron `30 6 * * *` (`UTC`) with instruction: "Run the morning store shrink and zero-scan phantom inventory sweep via scripts/store_shrink_task_ranker.py and produce prioritized cycle-count lists per store manager.""*

## Example Queries & Verified Outcomes

- **`store-ops-shrink-copilot`** ([skill guide](skills/store-ops-shrink-copilot/README.md)): Connector prompt: *"Analyze Northstar Retail store SKU snapshot where STR-104 has 18 units on hand with 7 zero-scan days and STR-109 has MISSING POS poll."* Verified starter check against `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` (`135.1 ms`): `records_scanned=3`, `stores_covered=3`, `total_shrink_usd=2885.0`, `phantom_inventory_count=1`.
- **`merchandising-assortment-planner`** ([skill guide](skills/merchandising-assortment-planner/README.md)): Connector prompt: *"Evaluate Northstar Retail 7-day beverage promo with $18k cannibalization loss and $12k media spend against 28-day baseline."* Verified starter check against `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` (`133.3 ms`): `campaigns_evaluated=2`, `profitable_count=1`, `margin_destructive_count=1`, `total_net_incremental_gm_usd=-350.0`.
- **`supplier-otif-chargeback-auditor`** ([skill guide](skills/supplier-otif-chargeback-auditor/README.md)): Connector prompt: *"Audit Northstar Retail PO arriving 95 minutes late with 180 minutes dock dwell and 90% fill rate."* Verified starter check against `Apex_Retail_Shrink_Promo_and_OTIF_Sample.xlsx` (`138.4 ms`): `po_deliveries_audited=3`, `overall_otif_pct=66.67`, `target_otif_pct=95.0`, `total_chargebacks_usd=3017.5`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-17`** (`6 tabs, 6,206 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.979 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`FAIL 0.756 / 1.000`) and `Prose-Only Baseline` (`FAIL 0.325 / 0.000`). Verified domain traps: Excluding stores with MISSING POS poll status before blaming shrink; Cannibalization/discount margin destruction detection; Vendor OTIF shortfall + yard dwell detention fee net recovery.
