# Deal Desk, RFP & Pipeline Hygiene Engine (`deal-desk-rfp-engine`)

Accelerates RFP security/compliance questionnaires with TF-IDF answer matching, validates multi-year SaaS quote discounts and gross margins against Deal Desk approval tiers, and audits CRM pipeline for slippage and multi-currency traps. Pairs live `/work` connectors (`Salesforce, Google Drive, Google Docs, Google Sheets, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams), Gmail`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Solutions Architect / Presales Lead | Completing 100+ row enterprise security, SOC2, and GDPR RFP workbooks | [`rfp-questionnaire-responder`](skills/rfp-questionnaire-responder/README.md) | `scripts/rfp_matrix_builder.py` |
| Deal Desk Manager | Auditing quarter-end enterprise quotes with non-standard Net-90 terms or high discounts | [`deal-desk-quote-guard`](skills/deal-desk-quote-guard/README.md) | `scripts/deal_margin_validator.py` |
| VP of Sales / RevOps Director | Running weekly global forecast inspections across USD/EUR/GBP territories | [`pipeline-hygiene-slippage`](skills/pipeline-hygiene-slippage/README.md) | `scripts/pipeline_slippage_auditor.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`deal-desk-rfp-engine.zip`](../../dist/bundles/deal-desk-rfp-engine.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/rfp-questionnaire-responder.zip`](../../dist/skills/rfp-questionnaire-responder.zip) — Matches RFP requirement rows against verified answer libraries using TF-IDF cosine similarity and flags mandatory compliance gaps.
  - [`dist/skills/deal-desk-quote-guard.zip`](../../dist/skills/deal-desk-quote-guard.zip) — Computes net effective discount, multi-year ramp ACV/TCV, gross margin floor compliance, non-standard terms, and required Deal Desk tier.
  - [`dist/skills/pipeline-hygiene-slippage.zip`](../../dist/skills/pipeline-hygiene-slippage.zip) — Audits CRM opportunities for stage staleness, push counts, missing MEDDPICC commit gates, single-threading, and multi-currency FX alignment.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`deal-desk-rfp-engine.zip`](../../dist/bundles/deal-desk-rfp-engine.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/deal-desk-rfp-engine` / `@deal-desk-rfp-engine` so Layer 1 (`remote_cli mcp`) pulls live data from `Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` (`6,190 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Pipeline_Opportunities`, `Quotes_Pricing_Desk`, `Quote_Line_Items`, `RFP_Questions`, `Answer_Library`, `FX_Rates_TCURR`)](../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx):

```bash
python3 plugins/deal-desk-rfp-engine/skills/rfp-questionnaire-responder/scripts/rfp_matrix_builder.py \
  --input examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx \
  --config plugins/deal-desk-rfp-engine/skills/rfp-questionnaire-responder/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Salesforce`, `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Gmail`.
- **Connector Fetch Guidance**: Query Salesforce opportunities, DatedConversionRate FX tables, and quote line items via remote_cli mcp salesforce, plus RFP questionnaires and Deal Desk approvals from Google Drive or SharePoint before Python validation.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` (`6,190 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Pipeline_Opportunities`, `Quotes_Pricing_Desk`, `Quote_Line_Items`, `RFP_Questions`, `Answer_Library`, `FX_Rates_TCURR`)](../../examples/deal-desk-rfp-engine/Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`deal-desk-approval-baseline.md`](../../shared/baselines/deal-desk-approval-baseline.md), [`commercial-contract-baseline.md`](../../shared/baselines/commercial-contract-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`salesforce-crm-soql-traps.md`](../../shared/traps/salesforce-crm-soql-traps.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Updating Salesforce opportunity forecast categories, close dates, or approved quote statuses; Submitting Deal Desk discount/non-standard term exceptions for CFO or VP Sales approval; Sending completed customer RFP responses or commercial quote emails externally via Gmail/Outlook.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Mandatory DatedConversionRate FX normalization across mixed-currency CRM rollups; Zero-guess abstention when approved RFP answer library contains no verified match; Indirect prompt-injection directive quarantine inside external customer RFP rows.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly Pipeline Hygiene Audit" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly Salesforce pipeline hygiene and slippage audit using scripts/pipeline_slippage_auditor.py. Normalize multi-currency opportunities, identify stale stages, >=2 push-count deals, single-threaded Commit opportunities, and StageName/IsClosed inconsistencies without modifying CRM records autonomously.""*

## Example Queries & Verified Outcomes

- **`rfp-questionnaire-responder`** ([skill guide](skills/rfp-questionnaire-responder/README.md)): Connector prompt: *"Complete Cymbal Financial's 25-row vendor security RFP using our Shared Drive Verified Q&A Library and list mandatory gaps."* Verified starter check against `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` (`146.7 ms`): `question_count=3`, `matched_count=2`, `unmatched_count=1`, `mandatory_gap_count=1`.
- **`deal-desk-quote-guard`** ([skill guide](skills/deal-desk-quote-guard/README.md)): Connector prompt: *"Evaluate Northstar Retail's 3-year ramped Salesforce quote (Y1 $80k, Y2 $180k, Y3 $260k) with Net 60 payment terms."* Verified starter check against `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` (`143.6 ms`): `quote_count=3`, `tier3_escalation_count=1`, `margin_floor_breach_count=1`, `total_net_tcv_usd=1476000.0`.
- **`pipeline-hygiene-slippage`** ([skill guide](skills/pipeline-hygiene-slippage/README.md)): Connector prompt: *"Audit our Q4 Salesforce Commit and BestCase deals across US (USD), EU (EUR), and Japan (JPY) against $4.0M remaining quota."* Verified starter check against `Apex_Deal_Desk_Pipeline_and_RFP_Sample.xlsx` (`145.7 ms`): `target_currency=USD`, `total_records_fetched=4`, `open_pipeline_count=4`, `closed_excluded_count=0`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-02`** (`6 tabs, 4,813 rows (.xlsx) + 28-page PDF`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.980 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.880 / 1.000`) and `Prose-Only Baseline` (`FAIL 0.794 / 0.667`). Verified domain traps: Tier-3 CFO approval trigger (38% discount + Net-90 + TfC); Single-threaded Commit pipeline slippage ($840k); GDPR Art.17 cold-storage backup erasure 90-day TTL gap.
