# Industrial Shopfloor Reliability, Quality & EHS Safety (`industrial-shopfloor-maintenance`)

Optimizes critical spare-part safety stocks and reorder points via censored MTBF reliability modeling, builds 80/20 scrap defect Paretos with CapEx payback evaluation, and enforces strict EHS Permit-to-Work LOTO and gas-test safety gates. Pairs live `/work` connectors (`BigQuery, Google Drive, Google Sheets, Google Docs`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Plant Maintenance & Reliability Engineer | Setting spare-parts reorder points (ROP) and safety stock across critical rotating assets | [`asset-reliability-spares-planner`](skills/asset-reliability-spares-planner/README.md) | `scripts/mtbf_spares_optimizer.py` |
| Plant Quality Director / Six Sigma Black Belt | Prioritizing shopfloor scrap categories and CapEx automation proposals | [`quality-capex-rca-copilot`](skills/quality-capex-rca-copilot/README.md) | `scripts/defect_pareto_correlator.py` |
| EHS Safety Officer / Shift Supervisor | Clearing Confined-Space, Hot-Work, and Lockout-Tagout (LOTO) maintenance permits | [`ehs-safety-permit-auditor`](skills/ehs-safety-permit-auditor/README.md) | `scripts/hse_permit_checker.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`industrial-shopfloor-maintenance.zip`](../../dist/bundles/industrial-shopfloor-maintenance.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/asset-reliability-spares-planner.zip`](../../dist/skills/asset-reliability-spares-planner.zip) — Calculates right-censored MTBF, lead-time demand, safety stock, Reorder Point (ROP), and critical stockout expedite POs.
  - [`dist/skills/quality-capex-rca-copilot.zip`](../../dist/skills/quality-capex-rca-copilot.zip) — Builds 80/20 manufacturing scrap cost Paretos, isolates >=2x anomalous supplier lots, and computes CapEx payback hurdles.
  - [`dist/skills/ehs-safety-permit-auditor.zip`](../../dist/skills/ehs-safety-permit-auditor.zip) — Enforces zero-compromise LOTO isolation, confined-space O2 (19.5-23.5%), 0% LEL gas freshness, fire watch, and worker certification checks.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`industrial-shopfloor-maintenance.zip`](../../dist/bundles/industrial-shopfloor-maintenance.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/industrial-shopfloor-maintenance` / `@industrial-shopfloor-maintenance` so Layer 1 (`remote_cli mcp`) pulls live data from `BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs` or `SAP PM / Shopfloor Historian & EHS Permit MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` (`4,812 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Plant_EHS_Permits_Ledger`, `Spare_Parts_MTBF_Master`, `Quality_Scrap_Events`, `Quality_CAPEX_Proposals`)](../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx):

```bash
python3 plugins/industrial-shopfloor-maintenance/skills/asset-reliability-spares-planner/scripts/mtbf_spares_optimizer.py \
  --input examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx \
  --config plugins/industrial-shopfloor-maintenance/skills/asset-reliability-spares-planner/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`.
- **Customer BYO-MCP Servers**: `SAP PM / Shopfloor Historian & EHS Permit MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Extract equipment work-order MTBF logs, spares inventory balances, QMS scrap batches, and EHS confined-space permit readings from BigQuery or customer SAP PM / Historian MCP servers via remote_cli mcp before Python safety and optimization runs.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` (`4,812 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Plant_EHS_Permits_Ledger`, `Spare_Parts_MTBF_Master`, `Quality_Scrap_Events`, `Quality_CAPEX_Proposals`)](../../examples/industrial-shopfloor-maintenance/Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`finance-materiality-baseline.md`](../../shared/baselines/finance-materiality-baseline.md), [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`bigquery-sap-erp-traps.md`](../../shared/traps/bigquery-sap-erp-traps.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`servicenow-jira-itsm-traps.md`](../../shared/traps/servicenow-jira-itsm-traps.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Creating spare-parts purchase requisitions in customer SAP PM / ERP MCP; Signing or authorizing live Permit-to-Work (LOTO / confined space) clearances in EHS MCP.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Hard STOP_WORK_BLOCKED interlock whenever O2 < 19.5%/> 23.5%, LEL >= 10%, H2S/CO threshold breach, or missing LOTO verification; Zero-stock critical asset safety-stock floor and MTBF reorder-point calculation; Pareto 80/20 scrap concentration correlation and discounted CapEx payback bounds.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Daily Critical Spares ROP Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the daily critical spare parts ROP check via scripts/mtbf_spares_optimizer.py across plant rotating equipment and flag zero-stock critical assets.""*

## Example Queries & Verified Outcomes

- **`asset-reliability-spares-planner`** ([skill guide](skills/asset-reliability-spares-planner/README.md)): Connector prompt: *"Check Apex Manufacturing compressor mechanical seals with 0 on-hand and 21-day lead time."* Verified starter check against `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` (`132.2 ms`): `parts_analyzed=3`, `critical_stockout_count=1`, `reorder_triggered_count=2`, `total_recommended_spend_usd=10080.0`.
- **`quality-capex-rca-copilot`** ([skill guide](skills/quality-capex-rca-copilot/README.md)): Connector prompt: *"Analyze Apex Manufacturing CNC plant scrap events across supplier lots and shifts."* Verified starter check against `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` (`134.3 ms`): `events_analyzed=3`, `total_scrap_cost_usd=222000.0`, `vital_80_defect_count=2`, `anomalous_lot_count=0`.
- **`ehs-safety-permit-auditor`** ([skill guide](skills/ehs-safety-permit-auditor/README.md)): Connector prompt: *"Audit Apex Manufacturing confined-space vessel permit PTW-101 with 90-min-old gas reading and loto_isolated=false."* Verified starter check against `Apex_Industrial_EHS_Spares_and_CAPEX_Sample.xlsx` (`132.7 ms`): `permits_audited=3`, `stop_work_blocked_count=2`, `eligible_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-15`** (`7 tabs, 5,309 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.980 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`FAIL 0.790 / 0.625`) and `Prose-Only Baseline` (`FAIL 0.784 / 0.625`). Verified domain traps: Hard O2 (<19.5%) & LOTO stop-work permit gate; Criticality floor overriding zero-failure safety-stock zero-out (TURBINE-SEAL-88); 80/20 scrap cost Pareto ranking (Porosity Void #1).
