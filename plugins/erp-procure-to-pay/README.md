# ERP Procure-to-Pay, GR/IR Clearing & Tariff Cost Engine (`erp-procure-to-pay`)

Reconciles SAP GR/IR clearing imbalances across goods receipts and invoice postings with TCURX scaling, simulates multi-supplier RFx total landed cost under tariff shocks, and rolls up multi-level BOM purchase price variances with cycle detection. Pairs live `/work` connectors (`BigQuery, Google Drive, Google Sheets, Gmail, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| SAP Materials Management / Close Accountant | Reconciling aged Goods Receipt / Invoice Receipt (`WRX` / `F.13` / `MR11`) suspense balances | [`gr-ir-clearing-orchestrator`](skills/gr-ir-clearing-orchestrator/README.md) | `scripts/gr_ir_reconciler.py` |
| Strategic Sourcing / Commodity Manager | Re-evaluating global vendor awards under sudden tariff hikes (`+25%`) and terms differences | [`supplier-rfx-tariff-modeler`](skills/supplier-rfx-tariff-modeler/README.md) | `scripts/landed_cost_simulator.py` |
| Cost Accounting / Manufacturing Finance Lead | Auditing multi-level bills of materials for standard cost rollups and purchase price variance (PPV) | [`bom-cost-rollup-variance`](skills/bom-cost-rollup-variance/README.md) | `scripts/bom_ppv_rollup.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`erp-procure-to-pay.zip`](../../dist/bundles/erp-procure-to-pay.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/gr-ir-clearing-orchestrator.zip`](../../dist/skills/gr-ir-clearing-orchestrator.zip) — Reconciles SAP WE goods receipts and RE invoice postings with TCURX currency scaling, SHKZG sign flips, and >60d aging classification.
  - [`dist/skills/supplier-rfx-tariff-modeler.zip`](../../dist/skills/supplier-rfx-tariff-modeler.zip) — Simulates multi-supplier RFx bids across FOB, freight, tariffs, shock scenarios, payment financing, and quality defect penalties.
  - [`dist/skills/bom-cost-rollup-variance.zip`](../../dist/skills/bom-cost-rollup-variance.zip) — Explodes multi-level BOMs with scrap factors, guards against circular BOM graphs, and rolls up leaf PPV drivers.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`erp-procure-to-pay.zip`](../../dist/bundles/erp-procure-to-pay.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/erp-procure-to-pay` / `@erp-procure-to-pay` so Layer 1 (`remote_cli mcp`) pulls live data from `BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` or `SAP S/4HANA / Oracle ERP & PLM BOM MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` (`5,354 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `MultiLevel_BOM_Edges`, `SKU_Item_Master_Costs`, `Supplier_RFx_Tariff_Bids`, `GR_IR_Clearing_Postings`, `FX_Rates_TCURR`)](../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx):

```bash
python3 plugins/erp-procure-to-pay/skills/gr-ir-clearing-orchestrator/scripts/gr_ir_reconciler.py \
  --input examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx \
  --config plugins/erp-procure-to-pay/skills/gr-ir-clearing-orchestrator/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `BigQuery`, `Google Drive`, `Google Sheets`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`.
- **Customer BYO-MCP Servers**: `SAP S/4HANA / Oracle ERP & PLM BOM MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Extract EKBE PO/GR/IR history tables, multi-level BOM explosions, and supplier RFx bids from BigQuery or customer SAP/Oracle ERP MCP servers (or Drive/SharePoint exports) via remote_cli mcp before running Python cost and clearing engines.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` (`5,354 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `MultiLevel_BOM_Edges`, `SKU_Item_Master_Costs`, `Supplier_RFx_Tariff_Bids`, `GR_IR_Clearing_Postings`, `FX_Rates_TCURR`)](../../examples/erp-procure-to-pay/Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`finance-materiality-baseline.md`](../../shared/baselines/finance-materiality-baseline.md) and [`bigquery-sap-erp-traps.md`](../../shared/traps/bigquery-sap-erp-traps.md), [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Posting SAP MR11/F.13 GR/IR clearing entries impacting GL accruals via customer ERP MCP; Awarding supplier RFx purchase orders or updating standard BOM costs in ERP/PLM.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Prohibition on clearing IR_WITHOUT_GR lines lacking verified physical goods receipt; BOM cycle detection blocking circular assembly graphs from cost rollups and compound 1/(1-scrap) yield math; TCURX decimal scaling, SHKZG credit reversal handling, and single-source vendor concentration alerts.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Daily GR/IR Aging Watch" on cron `0 7 * * 1-5` (`UTC`) with instruction: "Execute weekday SAP GR/IR clearing aging check via scripts/gr_ir_reconciler.py to isolate IR_WITHOUT_GR blocks and >60 day accruals.""*

## Example Queries & Verified Outcomes

- **`gr-ir-clearing-orchestrator`** ([skill guide](skills/gr-ir-clearing-orchestrator/README.md)): Connector prompt: *"Reconcile Apex Manufacturing SAP EKBE GR/IR lines including JPY raw postings and SHKZG='H' reversals."* Verified starter check against `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` (`138.0 ms`): `po_lines_analyzed=3`, `cleared_count=1`, `open_imbalance_count=2`, `gr_without_ir_count=1`.
- **`supplier-rfx-tariff-modeler`** ([skill guide](skills/supplier-rfx-tariff-modeler/README.md)): Connector prompt: *"Model a +25% tariff shock on CN origin quotes vs VN and MX bids for Apex Manufacturing."* Verified starter check against `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` (`135.4 ms`): `annual_demand_units=50000.0`, `tariff_shock_applied_pct=25.0`, `bids_evaluated=3`, `lowest_landed_supplier=Monterrey Industrial Machining`.
- **`bom-cost-rollup-variance`** ([skill guide](skills/bom-cost-rollup-variance/README.md)): Connector prompt: *"Roll up 3-level pump assembly BOM standard vs actual PPV with 4% scrap on sub-assemblies."* Verified starter check against `Apex_Supply_Chain_BOM_RFx_and_GRIR_Sample.xlsx` (`140.7 ms`): `assemblies_rolled_up=1`, `cycle_count=0`, `total_extended_ppv_usd=10.56`, `alert_component_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-06`** (`6 tabs, 5,609 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`FAIL (0.709 comp / 0.667 WF)`** vs `Base Agent (No Plugin)` (`FAIL 0.555 / 0.333`) and `Prose-Only Baseline` (`FAIL 0.566 / 0.333`). Verified domain traps: 25% tariff shock supplier re-ranking across 50k units; Compound scrap yield math cost / (1 - scrap); Zero-decimal JPY TCURX + GR without IR / IR without GR imbalances.
