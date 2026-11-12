# Financial Services Credit, KYB/AML & Claims Underwriting (`fsi-credit-kyc-claims`)

Calculates commercial borrower DSCR, net leverage, and interest coverage under multi-shock stress scenarios, resolves multi-hop UBO beneficial ownership with AML velocity/structuring checks, and evaluates insurance claims deterministically. Pairs live `/work` connectors (`BigQuery, Snowflake, Google Drive, Google Docs, Google Sheets, Gmail`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Commercial Credit Underwriter | Preparing credit committee memos for leveraged mid-market corporate borrowers | [`commercial-credit-memo-analyst`](skills/commercial-credit-memo-analyst/README.md) | `scripts/credit_covenant_stress.py` |
| KYB / AML Financial Crimes Investigator | Tracing multi-hop corporate shell ownership and cross-border wire patterns | [`kyc-aml-screening-dossier`](skills/kyc-aml-screening-dossier/README.md) | `scripts/ubo_velocity_screener.py` |
| Complex Claims Adjuster (Cyber & Property) | Triaging incoming loss notifications against policy exclusions, deductibles, and sublimits | [`insurance-claims-triage-pack`](skills/insurance-claims-triage-pack/README.md) | `scripts/coverage_limit_evaluator.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`fsi-credit-kyc-claims.zip`](../../dist/bundles/fsi-credit-kyc-claims.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/commercial-credit-memo-analyst.zip`](../../dist/skills/commercial-credit-memo-analyst.zip) — Calculates DSCR, Net Leverage, Interest Coverage, and Current Ratio across Base, -10%/-20% revenue, and +200bps rate shocks.
  - [`dist/skills/kyc-aml-screening-dossier.zip`](../../dist/skills/kyc-aml-screening-dossier.zip) — Traverses multi-hop holding DAGs to compute cumulative UBO ownership %, enforces 10% EDD drop, and detects velocity/structuring spikes.
  - [`dist/skills/insurance-claims-triage-pack.zip`](../../dist/skills/insurance-claims-triage-pack.zip) — Validates policy effective periods and peril exclusions, computes deductible/coinsurance/sublimit payouts, and flags >$100k reserves.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`fsi-credit-kyc-claims.zip`](../../dist/bundles/fsi-credit-kyc-claims.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/fsi-credit-kyc-claims` / `@fsi-credit-kyc-claims` so Layer 1 (`remote_cli mcp`) pulls live data from `BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail` or `KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` (`5,695 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `UBO_Ownership_Registry`, `CrossBorder_Wire_Tx`, `Commercial_Borrower_Credit`, `Insurance_Loss_Claims`, `Policy_Coverage_Schedule`)](../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx):

```bash
python3 plugins/fsi-credit-kyc-claims/skills/commercial-credit-memo-analyst/scripts/credit_covenant_stress.py \
  --input examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx \
  --config plugins/fsi-credit-kyc-claims/skills/commercial-credit-memo-analyst/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `BigQuery`, `Snowflake`, `Google Drive`, `Google Docs`, `Google Sheets`, `Gmail`.
- **Customer BYO-MCP Servers**: `KYB / Sanctions Screening & Core Banking / Claims Clearinghouse MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Retrieve borrower financials, corporate ownership graphs, wire ledger transactions, and policy claim schedules from BigQuery, Snowflake, or customer KYB/Claims MCP servers via remote_cli mcp before Python graph and covenant checks.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` (`5,695 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `UBO_Ownership_Registry`, `CrossBorder_Wire_Tx`, `Commercial_Borrower_Credit`, `Insurance_Loss_Claims`, `Policy_Coverage_Schedule`)](../../examples/fsi-credit-kyc-claims/Apex_FSI_Credit_AML_and_Claims_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`fsi-credit-kyc-baseline.md`](../../shared/baselines/fsi-credit-kyc-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`bigquery-sap-erp-traps.md`](../../shared/traps/bigquery-sap-erp-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Submitting commercial credit underwriting decisions or covenant waivers in core banking/LOS MCP; Filing regulatory SAR/STR narratives or freezing customer banking accounts via AML MCP; Authorizing claim settlement reserve releases or disbursement payouts via Claims MCP.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Transitive ownership graph multiplication catching sub-threshold pass-through structures (>=10% EDD / >=25% UBO); Sub-$10k structuring velocity burst detection and hard base/stress DSCR & leverage covenant breaches; Per-occurrence deductible, coverage sublimit, and policy exclusion net indemnity math.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Daily KYB Velocity & Structuring Watch" on cron `0 5 * * *` (`UTC`) with instruction: "Run the daily AML transaction velocity and structuring sweep via scripts/ubo_velocity_screener.py across active corporate banking accounts and flag EDD alerts for MLRO review.""*

## Example Queries & Verified Outcomes

- **`commercial-credit-memo-analyst`** ([skill guide](skills/commercial-credit-memo-analyst/README.md)): Connector prompt: *"Stress-test Cymbal Financial's borrower spread with $12M EBITDA, $42M floating debt, under -20% revenue and +200bps."* Verified starter check against `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` (`135.8 ms`): `borrowers_evaluated=2`, `base_breach_count=0`, `stress_breach_count=1`, `clean_pass_count=1`.
- **`kyc-aml-screening-dossier`** ([skill guide](skills/kyc-aml-screening-dossier/README.md)): Connector prompt: *"Trace Cymbal Financial onboarding entity owned via two 60%/50% indirect holding layers registered in KY."* Verified starter check against `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` (`139.4 ms`): `ubo_threshold_applied_pct=10.0`, `edd_triggered=True`, `identified_ubo_count=2`, `velocity_multiplier=3.84`.
- **`insurance-claims-triage-pack`** ([skill guide](skills/insurance-claims-triage-pack/README.md)): Connector prompt: *"Evaluate $350k ransomware claim with $25k deductible, $150k cyber sublimit, and 80% coinsurance."* Verified starter check against `Apex_FSI_Credit_AML_and_Claims_Sample.xlsx` (`139.0 ms`): `claims_triaged=3`, `denied_count=1`, `reserve_escalation_count=1`, `total_claimed_usd=650000.0`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-07`** (`6 tabs, 5,806 rows (.xlsx)`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.912 comp / 0.818 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.869 / 0.727`) and `Prose-Only Baseline` (`PASS 0.837 / 0.727`). Verified domain traps: Transitive equity multiplication with lowered 10% Cayman EDD UBO threshold; Sub-$10,000 wire structuring count & 3.84x velocity spike; DSCR/Net Leverage Watch Zone vs Stress Covenant Breach; Cyber ransomware $150k policy sublimit cap + flood exclusion denial.
