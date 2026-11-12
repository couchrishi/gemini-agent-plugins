# Finance Variance, 3-Way Match & AR Reconciliation (`finance-variance-recon`)

Reconciles AP 3-way PO/GR/Invoice matches with SAP TCURX/SHKZG guards and duplicate/bank-change fraud holds, builds constant-currency P&L variance bridges without summary double-counting, and audits AR aging buckets with strict credit-memo isolation. Pairs live `/work` connectors (`BigQuery, Google Drive, Google Sheets, Google Docs, Gmail, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| AP Controller / Shared Services Lead | Reconciling SAP S/4HANA or Oracle purchase orders, goods receipts, and vendor invoices | [`ap-three-way-match`](skills/ap-three-way-match/README.md) | `scripts/reconcile_3way.py` |
| Corporate FP&A Controller | Bridging Q3/FY actuals vs budget across hierarchical general ledger extracts | [`pnl-budget-variance-bridge`](skills/pnl-budget-variance-bridge/README.md) | `scripts/pnl_variance_engine.py` |
| Order-to-Cash (O2C) Credit Manager | Prioritizing collections worklists and calculating clean DSO ahead of close | [`ar-aging-collections-audit`](skills/ar-aging-collections-audit/README.md) | `scripts/aging_bucket_auditor.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`finance-variance-recon.zip`](../../dist/bundles/finance-variance-recon.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/ap-three-way-match.zip`](../../dist/skills/ap-three-way-match.zip) — Performs deterministic PO/GR/Invoice 3-way matching with SAP TCURX decimal normalization, SHKZG sign handling, duplicate invoice detection, and bank-change fraud holds.
  - [`dist/skills/pnl-budget-variance-bridge.zip`](../../dist/skills/pnl-budget-variance-bridge.zip) — Computes P&L Actual vs Budget/Forecast variance bridges split by constant-FX vs currency impact while enforcing leaf-vs-summary hierarchy tie-outs.
  - [`dist/skills/ar-aging-collections-audit.zip`](../../dist/skills/ar-aging-collections-audit.zip) — Buckets open accounts receivable across Current to 90+ days while isolating unapplied credit memos so negative rows never mask delinquent balances.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`finance-variance-recon.zip`](../../dist/bundles/finance-variance-recon.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/finance-variance-recon` / `@finance-variance-recon` so Layer 1 (`remote_cli mcp`) pulls live data from `BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` or `SAP S/4HANA / Oracle ERP MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` (`6,816 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `PO_Line_Items_EKPO`, `Goods_Receipts_EKBE`, `Vendor_Invoices_RBKP`, `Consolidated_GL_Actuals`, `AR_Open_Receivables`, `FX_Rates_TCURR`)](../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx):

```bash
python3 plugins/finance-variance-recon/skills/ap-three-way-match/scripts/reconcile_3way.py \
  --input examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx \
  --config plugins/finance-variance-recon/skills/ap-three-way-match/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `BigQuery`, `Google Drive`, `Google Sheets`, `Google Docs`, `Gmail`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`.
- **Customer BYO-MCP Servers**: `SAP S/4HANA / Oracle ERP MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Pull PO, Goods Receipt, Invoice, GL actual/budget hierarchy, and AR open-item ledgers from BigQuery, Google Sheets, SharePoint, or customer SAP/Oracle ERP MCP servers via remote_cli mcp before running Python reconciliation engines.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` (`6,816 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `PO_Line_Items_EKPO`, `Goods_Receipts_EKBE`, `Vendor_Invoices_RBKP`, `Consolidated_GL_Actuals`, `AR_Open_Receivables`, `FX_Rates_TCURR`)](../../examples/finance-variance-recon/Apex_Finance_3Way_PnL_and_AR_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`finance-materiality-baseline.md`](../../shared/baselines/finance-materiality-baseline.md) and [`bigquery-sap-erp-traps.md`](../../shared/traps/bigquery-sap-erp-traps.md), [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Releasing AP invoice payment batches or posting GL/AP entries via customer ERP MCP; Updating vendor remittance or bank master records in ERP (never auto-executed from email); Sending external customer AR collections or dunning emails via Gmail or Outlook.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: TCURX zero/3-decimal scaling (JPY/KRW x100, KWD/BHD x0.1), SHKZG='H' sign inversion, and BEC bank-change FRAUD_HOLD; GL summary-vs-leaf exclusion preventing parent rollup double-counting beyond hierarchy_tolerance_amount; AR credit-memo isolation so negative credits never mask 90+ days past-due delinquency.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Daily AP & GR/IR Exception Watch" on cron `0 6 * * 1-5` (`UTC`) with instruction: "Run the weekday morning AP 3-way match sweep using scripts/reconcile_3way.py across open vendor invoices, purchase orders, and goods receipts. Surface duplicate invoice suspects, bank-change holds, TCURX decimal mismatches, and price/quantity exceptions for AP Controller review without releasing payments.""*

## Example Queries & Verified Outcomes

- **`ap-three-way-match`** ([skill guide](skills/ap-three-way-match/README.md)): Connector prompt: *"Run AP 3-way match on Apex Manufacturing's JPY and USD invoices from SAP OData."* Verified starter check against `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` (`151.1 ms`): `invoices_evaluated=7`, `matched_count=3`, `credit_memo_count=1`, `exception_hold_count=3`.
- **`pnl-budget-variance-bridge`** ([skill guide](skills/pnl-budget-variance-bridge/README.md)): Connector prompt: *"Build the Northstar Retail Q3 P&L constant-currency variance bridge from BigQuery GL actuals containing both parent rollup and leaf rows."* Verified starter check against `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` (`146.1 ms`): `leaf_line_count=6`, `summary_rows_excluded_from_rollup=2`, `hierarchy_break_count=1`, `actual_revenue_usd=42500000.0`.
- **`ar-aging-collections-audit`** ([skill guide](skills/ar-aging-collections-audit/README.md)): Connector prompt: *"Audit Veloce SuperApp's open AR subledger where a major customer has a $45k `90+` invoice alongside a `-40k` credit memo."* Verified starter check against `Apex_Finance_3Way_PnL_and_AR_Sample.xlsx` (`149.1 ms`): `customer_count=4`, `gross_positive_ar_usd=692000.0`, `unapplied_credits_usd=-18500.0`, `net_ar_usd=673500.0`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-01`** (`7 tabs, 5,403 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.893 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`FAIL 0.302 / 0.000`) and `Prose-Only Baseline` (`PASS 0.889 / 0.800`). Verified domain traps: SAP TCURX zero-decimal JPY scaling (x100); SAP SHKZG='H' debit/credit sign reversal; Parent summary hierarchy double-counting (REV-TOT/OPEX-TOT); Unapplied AR credit deduction before DSO.
