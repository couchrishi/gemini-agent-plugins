# GSI Proposal Architecture, SOW Margin & Bench Factory (`gsi-proposal-ip-factory`)

Models consulting delivery staffing pyramids and onshore/offshore margin leverage, audits SOW drafts for scope creep phrasing and margin breaches, and matches open project roles to bench consultants. Pairs live `/work` connectors (`Google Drive, Google Docs, Google Sheets, Google Slides, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| GSI Solution Architect / Pursuit Lead | Sizing multi-phase delivery pyramids, blended rates, and offshore leverage ratios for enterprise RFPs | [`winning-proposal-architect`](skills/winning-proposal-architect/README.md) | `scripts/staffing_pyramid_calculator.py` |
| Consulting Commercial Counsel / Engagement Partner | Auditing Statements of Work before signature to eliminate uncapped scope creep | [`sow-scope-margin-auditor`](skills/sow-scope-margin-auditor/README.md) | `scripts/sow_margin_linter.py` |
| Resource Management / Workforce Planning Lead | Matching open project roles against certified internal bench consultants | [`bench-skill-demand-matcher`](skills/bench-skill-demand-matcher/README.md) | `scripts/talent_bench_matcher.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`gsi-proposal-ip-factory.zip`](../../dist/bundles/gsi-proposal-ip-factory.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/winning-proposal-architect.zip`](../../dist/skills/winning-proposal-architect.zip) — Calculates multi-phase effort hours, onshore/offshore leverage ratio, blended bill rate, and gross margin vs SOW floor.
  - [`dist/skills/sow-scope-margin-auditor.zip`](../../dist/skills/sow-scope-margin-auditor.zip) — Lints SOW drafts for unbounded 'all work required' obligations, missing acceptance criteria, >10d deemed acceptance, and margin floors.
  - [`dist/skills/bench-skill-demand-matcher.zip`](../../dist/skills/bench-skill-demand-matcher.zip) — Matches open project seats against bench skills, roll-off dates, location overlap, and target role margin.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`gsi-proposal-ip-factory.zip`](../../dist/bundles/gsi-proposal-ip-factory.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/gsi-proposal-ip-factory` / `@gsi-proposal-ip-factory` so Layer 1 (`remote_cli mcp`) pulls live data from `Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)` or `Workday HRIS & PSA Staffing MCP server`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` (`6,000 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Proposal_Phase_Pyramid`, `Role_Rate_Card_Allocations`, `Bench_Consultant_Roster`, `Staffing_Demand_Pipeline`, `SOW_Deliverables`, `SOW_Clauses`)](../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx):

```bash
python3 plugins/gsi-proposal-ip-factory/skills/winning-proposal-architect/scripts/staffing_pyramid_calculator.py \
  --input examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx \
  --config plugins/gsi-proposal-ip-factory/skills/winning-proposal-architect/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`.
- **Customer BYO-MCP Servers**: `Workday HRIS & PSA Staffing MCP server` (discovered dynamically via `remote_cli mcp <connector> list-tools`).
- **Connector Fetch Guidance**: Pull rate cards, SOW milestone drafts, and RFP requirements from Google Drive/SharePoint plus consultant skill inventories and clearance eligibility from Workday/PSA MCP servers via remote_cli mcp before Python staffing and margin checks.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` (`6,000 B`, `.xlsx` workbook with tabs: `Parameters_Config`, `Proposal_Phase_Pyramid`, `Role_Rate_Card_Allocations`, `Bench_Consultant_Roster`, `Staffing_Demand_Pipeline`, `SOW_Deliverables`, `SOW_Clauses`)](../../examples/gsi-proposal-ip-factory/Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`commercial-contract-baseline.md`](../../shared/baselines/commercial-contract-baseline.md), [`deal-desk-approval-baseline.md`](../../shared/baselines/deal-desk-approval-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`chain-denominator-seams.md`](../../shared/traps/chain-denominator-seams.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md), [`sharepoint-onedrive-kql-traps.md`](../../shared/traps/sharepoint-onedrive-kql-traps.md), [`workday-hris-traps.md`](../../shared/traps/workday-hris-traps.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Submitting below-margin or high-risk SOW bids for Practice VP / Finance sign-off in PSA MCP; Assigning bench consultants or initiating subcontractor requisitions in Workday/PSA MCP; Sending client proposal decks or redlined SOWs externally via Gmail or Outlook.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Onshore/offshore leverage ratio, blended cost/bill rate, and hard minimum gross-margin floor guard; Mandatory security-clearance and availability window matching before bench allocation; Unlimited-revisions and deemed-acceptance SOW legal/margin risk clause flagging.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly Bench Utilization Digest" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly bench-to-demand skill matching check via scripts/talent_bench_matcher.py and surface unfilled roles needing subcontractor sourcing.""*

## Example Queries & Verified Outcomes

- **`winning-proposal-architect`** ([skill guide](skills/winning-proposal-architect/README.md)): Connector prompt: *"Model Stratos Telecom CRM migration staffing pyramid in Drive with 25% offshore leverage and 26% gross margin."* Verified starter check against `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` (`166.0 ms`): `total_effort_hours=4320.0`, `offshore_leverage_pct=74.07`, `below_offshore_target=False`, `total_revenue_usd=594880.0`.
- **`sow-scope-margin-auditor`** ([skill guide](skills/sow-scope-margin-auditor/README.md)): Connector prompt: *"Audit CivicFirst Agency SOW draft containing 'all work required at no additional cost regardless' and 18% margin."* Verified starter check against `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` (`139.5 ms`): `sow_id=SOW-APX-GSI-2026-09`, `fixed_fee_usd=1850000.0`, `estimated_cost_usd=1420000.0`, `gross_margin_pct=23.24`.
- **`bench-skill-demand-matcher`** ([skill guide](skills/bench-skill-demand-matcher/README.md)): Connector prompt: *"Match Cascade State University project demands against Workday bench roster where SAP Basis lacks local coverage."* Verified starter check against `Apex_GSI_Proposal_Bench_and_SOW_Sample.xlsx` (`135.4 ms`): `demands_evaluated=2`, `consultants_screened=3`, `filled_internally_count=2`, `external_subcontract_required_count=0`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-13`** (`5 tabs, 4,109 rows (.xlsx) + 27-page .docx`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.830 comp / 0.667 WF)`** vs `Base Agent (No Plugin)` (`FAIL 0.745 / 0.667`) and `Prose-Only Baseline` (`FAIL 0.714 / 0.667`). Verified domain traps: Named phases vs 50-row synthetic Workstream Wave effort rollup; Skill/availability/clearance bench matching (CON-APX-101/102); Fixed-fee SOW unlimited revisions & deemed-acceptance risk.
