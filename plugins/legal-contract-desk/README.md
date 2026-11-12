# Legal Contract Desk & Regulatory Compliance (`legal-contract-desk`)

Redlines commercial NDAs, MSAs, and DPAs against 1/3/9 risk playbooks, calculates exact auto-renewal opt-out deadlines and escalator caps from executed contracts, and maps regulatory articles against internal control inventories. Pairs live `/work` connectors (`Google Drive, Google Docs, Google Sheets, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams), Box, ServiceNow, Gmail`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Commercial Counsel / Contracts Manager | Redlining counterparty MSAs and DPAs against corporate risk tolerances | [`contract-playbook-redliner`](skills/contract-playbook-redliner/README.md) | `scripts/clause_risk_matrix.py` |
| Legal Ops / Contract Administrator | Monitoring executed vendor renewals, auto-renewal opt-out deadlines, and CPI uplifts | [`executed-obligation-extractor`](skills/executed-obligation-extractor/README.md) | `scripts/obligation_calendar_builder.py` |
| GRC / InfoSec Compliance Lead | Mapping incoming EU AI Act, GDPR, DORA, or SOC2 obligations onto internal controls | [`regulatory-change-mapper`](skills/regulatory-change-mapper/README.md) | `scripts/control_gap_mapper.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`legal-contract-desk.zip`](../../dist/bundles/legal-contract-desk.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/contract-playbook-redliner.zip`](../../dist/skills/contract-playbook-redliner.zip) — Scores commercial contract clauses on a 1/3/9 risk scale against playbook rules, flags walk-away blockers, and generates fallback redlines.
  - [`dist/skills/executed-obligation-extractor.zip`](../../dist/skills/executed-obligation-extractor.zip) — Calculates exact notice deadlines prior to auto-renewal, flags CPI escalator breaches, and builds executed obligation calendars.
  - [`dist/skills/regulatory-change-mapper.zip`](../../dist/skills/regulatory-change-mapper.zip) — Maps regulatory articles against internal controls to detect uncovered mandates, stale test evidence, and prioritized remediation queues.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`legal-contract-desk.zip`](../../dist/bundles/legal-contract-desk.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/legal-contract-desk` / `@legal-contract-desk` so Layer 1 (`remote_cli mcp`) pulls live data from `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_MSA_Obligations_and_Compliance_Sample.docx` (`4,941 B`, `.docx` document with `8` embedded tables)](../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx):

```bash
python3 plugins/legal-contract-desk/skills/contract-playbook-redliner/scripts/clause_risk_matrix.py \
  --input examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx \
  --config plugins/legal-contract-desk/skills/contract-playbook-redliner/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Box`, `ServiceNow`, `Gmail`.
- **Connector Fetch Guidance**: Fetch counterparty MSAs/DPAs, multi-tab Google Docs playbooks, executed contract registers, and GRC regulatory control sheets from Drive, SharePoint, Box, or ServiceNow via remote_cli mcp before running Python clause and obligation engines.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_MSA_Obligations_and_Compliance_Sample.docx` (`4,941 B`, `.docx` document with `8` embedded tables)](../../examples/legal-contract-desk/Apex_MSA_Obligations_and_Compliance_Sample.docx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`commercial-contract-baseline.md`](../../shared/baselines/commercial-contract-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md), [`sharepoint-onedrive-kql-traps.md`](../../shared/traps/sharepoint-onedrive-kql-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Sending redlined contract drafts or counter-proposals to external counterparty counsel via Gmail/Outlook; Updating GRC compliance control statuses or legal approval records in ServiceNow.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Unilateral Score 9 walk-away blocker detection (AI training carve-outs, uncapped liability, shortened breach notice); Indirect prompt-injection directive quarantine inside contract footnotes and exhibits; Deterministic opt-out notice deadline calculation (renewal_date - notice_days) and uncapped CPI escalation flags.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly Renewal & Notice Deadline Watch" on cron `0 8 * * 1` (`UTC`) with instruction: "Run the weekly executed contract renewal and obligation watch via scripts/obligation_calendar_builder.py. Compute exact opt-out notice deadlines (`renewal_date - notice_days`), surface urgent <=30 day windows and uncapped CPI escalators, and generate a draft reminder pack without emailing counterparties.""*

## Example Queries & Verified Outcomes

- **`contract-playbook-redliner`** ([skill guide](skills/contract-playbook-redliner/README.md)): Connector prompt: *"Review Cymbal Financial's incoming vendor MSA draft in Drive for 1/3/9 playbook compliance."* Verified starter check against `Apex_MSA_Obligations_and_Compliance_Sample.docx` (`149.2 ms`): `clauses_reviewed=5`, `blocker_score9_count=3`, `negotiable_score3_count=1`, `acceptable_score1_count=1`.
- **`executed-obligation-extractor`** ([skill guide](skills/executed-obligation-extractor/README.md)): Connector prompt: *"Audit all Apex Manufacturing executed supplier MSAs in SharePoint for upcoming opt-out deadlines."* Verified starter check against `Apex_MSA_Obligations_and_Compliance_Sample.docx` (`163.5 ms`): `contracts_audited=3`, `urgent_opt_out_count=1`, `expired_opt_out_count=1`, `unverified_missing_count=0`.
- **`regulatory-change-mapper`** ([skill guide](skills/regulatory-change-mapper/README.md)): Connector prompt: *"Map EU DORA operational resilience articles against our ServiceNow GRC control register for Cymbal Financial."* Verified starter check against `Apex_MSA_Obligations_and_Compliance_Sample.docx` (`145.7 ms`): `articles_evaluated=3`, `compliant_count=1`, `uncovered_gap_count=1`, `failing_or_stale_count=1`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-03`** (`27-page .docx + 24-page Playbook PDF`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.985 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.893 / 1.000`) and `Prose-Only Baseline` (`FAIL 0.377 / 0.000`). Verified domain traps: Unilateral liability cap & Sec 14.3(b) super-cap carve-out; 96h vs 72h GDPR / 48h playbook breach notice SLA; Permissive AI foundation-model training clause; Adversarial prompt injection in Footnote 11.4-a.
