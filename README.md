# Gemini Agent Plugins

[![Apache-2.0 License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Plugins](https://img.shields.io/badge/Plugins-20-1A73E8.svg)](.gemini-agent/catalog.json)
[![Workflow Skills](https://img.shields.io/badge/Skills-60-0F9D58.svg)](.gemini-agent/catalog.json)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](pyproject.toml)

Production-grade department plugins, single-hop workflow skills, deterministic Python computation engines, enterprise API trap guides, typed organization configuration schemas, and Common Expression Language (CEL) human-in-the-loop (HITL) safety guardrails built for **Gemini Enterprise** and **Gemini Agent**.

Every plugin solves real enterprise failure modes instead of wrapping thin prompts:
- **Deterministic Computation over LLM Arithmetic:** All 60 skills ship pure Python 3.11+ standard-library engines under `scripts/` designed to run inside Gemini Agent's persistent `pyrepl` RAM session (or `python3` CLI fallback).
- **Three-Mode Connector Degradation:** Every workflow operates across **Mode A** (live enterprise connectors: ServiceNow, Jira, Salesforce, SAP S/4HANA, Workday, BigQuery, SharePoint, GitHub), **Mode B** (Google Workspace fallback: Drive, Docs, Sheets, Slides, Gmail, Calendar), and **Mode C** (local `.json`/`.csv` upload).
- **Zero-Day Starter Baselines:** Every plugin ships `org_configured: false` in `references/config.json` paired with Day-1 industry baselines in `shared/baselines/` and stamps outputs with `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]` until tenant thresholds are bound via `tools/package.py --org-config`.
- **Enterprise API Trap Defenses:** Nine shared trap guides under `shared/traps/` encode pagination limits (`absent-is-not-zero.md`), cross-system denominator normalization (`chain-denominator-seams.md`), indirect prompt injection defense (`untrusted-content-and-pii.md`), and SAP/Workday/Salesforce/ServiceNow/SharePoint/Workspace data-shape quirks.

---

## Quickstart

### 1. Upload Ready-to-Use `.zip` Packages in Gemini Agent Web or Desktop

All 80 validated `.zip` archives live directly in [`dist/`](dist/manifest.json):

- **Option A — 1-Click Department Bundle (`dist/bundles/<plugin-id>.zip`, 20 bundles):**
  Upload one department bundle to give a general coworker agent all three workflows, shared API trap guides, starter baselines, and its bundled `references/config.json`.
  Example: upload [`dist/bundles/finance-variance-recon.zip`](dist/bundles/finance-variance-recon.zip) for AP 3-way match, P&L variance bridging, and AR collections aging.

- **Option B — Granular 1-Hop Custom Agent Skill (`dist/skills/<skill-id>.zip`, 60 skills):**
  Upload a single focused skill archive for tight Custom Agent instructions, predictable routing, and minimal context footprint.
  Example: upload [`dist/skills/ap-three-way-match.zip`](dist/skills/ap-three-way-match.zip) or [`dist/skills/kyc-aml-screening-dossier.zip`](dist/skills/kyc-aml-screening-dossier.zip).

### 2. Bind Your Organization Thresholds (Optional Tenant Stamp)

Customize materiality thresholds, SLA windows, discount approval tiers, F&A grant caps, or credit covenants without editing plugin source files:

```bash
cat <<'EOF' > /tmp/cymbal-org-config.json
{
  "organization_name": "Cymbal Financial",
  "global": {
    "materiality_amount_threshold": 10000.0
  },
  "plugins": {
    "finance-variance-recon": {
      "price_tolerance_pct": 0.015,
      "ar_escalation_90_plus_threshold": 5000.0
    },
    "fsi-credit-kyc-claims": {
      "min_dscr": 1.35,
      "max_net_leverage": 3.25
    }
  }
}
EOF

python3 tools/package.py --org-config /tmp/cymbal-org-config.json --output-dir /tmp/cymbal-dist
```

Any property bound through `--org-config` is validated against that plugin's `.gemini-plugin/config.schema.json`, sets `"org_configured": true` in `references/config.json`, and suppresses the standard baseline disclaimer banner across all JSON and Markdown outputs.

### 3. Local Validation & Test Execution

```bash
# Validate all 20 plugins, 60 skills, 80 dist zips, schemas, CEL guardrails, links, and public hygiene
make validate

# Check that materialized references and dist/ archives have zero drift
make check

# Execute the full pytest suite across all 60 computation scripts and packaging tests
make test
```

---

## Complete Catalog: 20 Plugins & 60 Skills

Canonical machine-readable index: [`.gemini-agent/catalog.json`](.gemini-agent/catalog.json).

### Horizontal Cross-Industry Plugins (10 Plugins, 30 Skills)

| # | Plugin | Category | Workflow Skills (`dist/skills/<id>.zip`) | Primary Connectors & Baselines |
| :--- | :--- | :--- | :--- | :--- |
| 1 | [`enterprise-knowledge-hub`](plugins/enterprise-knowledge-hub/README.md) | Horizontal | `cross-source-knowledge-synthesis`, `policy-sop-answering`, `knowledge-gap-freshness-audit` | Drive, SharePoint, Confluence, Jira; `itsm-sla-severity-baseline.md` |
| 2 | [`executive-briefing-ops`](plugins/executive-briefing-ops/README.md) | Horizontal | `daily-executive-briefing`, `meeting-to-execution-pack`, `stakeholder-account-prep` | Gmail, Calendar, Meet, Slack, Salesforce, Jira; `itsm-sla-severity-baseline.md` |
| 3 | [`itsm-command-center`](plugins/itsm-command-center/README.md) | Horizontal | `incident-triage-routing`, `change-risk-cab-review`, `problem-rca-kb-generator` | ServiceNow, Jira, Cloud Logging; `itsm-sla-severity-baseline.md` |
| 4 | [`deal-desk-rfp-engine`](plugins/deal-desk-rfp-engine/README.md) | Horizontal | `rfp-questionnaire-responder`, `deal-desk-quote-guard`, `pipeline-hygiene-slippage` | Salesforce, Drive, Sheets, Docs; `deal-desk-approval-baseline.md` |
| 5 | [`conversational-bi-analyst`](plugins/conversational-bi-analyst/README.md) | Horizontal | `schema-grounded-sql-analyst`, `kpi-anomaly-driver-tree`, `executive-data-story-pack` | BigQuery, Looker, Snowflake, Databricks, Sheets; `finance-materiality-baseline.md` |
| 6 | [`sdlc-modernization-sre`](plugins/sdlc-modernization-sre/README.md) | Horizontal | `legacy-code-to-prd`, `sre-incident-postmortem`, `security-pr-readiness-gate` | GitHub, GitLab, Jira, Cloud Logging; `itsm-sla-severity-baseline.md` |
| 7 | [`legal-contract-desk`](plugins/legal-contract-desk/README.md) | Horizontal | `contract-playbook-redliner`, `executed-obligation-extractor`, `regulatory-change-mapper` | Docs, Drive, SharePoint, Calendar; `commercial-contract-baseline.md` |
| 8 | [`finance-variance-recon`](plugins/finance-variance-recon/README.md) | Horizontal | `ap-three-way-match`, `pnl-budget-variance-bridge`, `ar-aging-collections-audit` | SAP S/4HANA, Oracle Fusion, BigQuery, Sheets; `finance-materiality-baseline.md` |
| 9 | [`people-ops-talent-hub`](plugins/people-ops-talent-hub/README.md) | Horizontal | `structured-hiring-rubric`, `employee-onboarding-navigator`, `workforce-attrition-comp-audit` | Workday, Calendar, Docs, Sheets; `hr-hiring-comp-baseline.md` |
| 10 | [`brand-campaign-studio`](plugins/brand-campaign-studio/README.md) | Horizontal | `brand-voice-compliance-gate`, `multimodal-campaign-brief`, `market-localization-adapter` | Drive, Docs, Slides, Sheets; `commercial-contract-baseline.md` |

### Enterprise Operations Plugins (3 Plugins, 9 Skills)

| # | Plugin | Category | Workflow Skills (`dist/skills/<id>.zip`) | Primary Connectors & Baselines |
| :--- | :--- | :--- | :--- | :--- |
| 11 | [`erp-procure-to-pay`](plugins/erp-procure-to-pay/README.md) | Enterprise Ops | `gr-ir-clearing-orchestrator`, `supplier-rfx-tariff-modeler`, `bom-cost-rollup-variance` | SAP S/4HANA, Oracle Fusion, BigQuery, Sheets; `finance-materiality-baseline.md` |
| 12 | [`gsi-proposal-ip-factory`](plugins/gsi-proposal-ip-factory/README.md) | Enterprise Ops | `winning-proposal-architect`, `sow-scope-margin-auditor`, `bench-skill-demand-matcher` | Workday, Salesforce, Drive, Sheets; `deal-desk-approval-baseline.md`, `commercial-contract-baseline.md` |
| 13 | [`customer-operations-escalation`](plugins/customer-operations-escalation/README.md) | Enterprise Ops | `critical-escalation-warroom`, `csat-churn-signal-miner`, `troubleshooting-tree-author` | Salesforce, Jira, ServiceNow, BigQuery; `itsm-sla-severity-baseline.md` |

### Industry Vertical Flagship Plugins (7 Plugins, 21 Skills)

| # | Plugin | Category | Workflow Skills (`dist/skills/<id>.zip`) | Primary Connectors & Baselines |
| :--- | :--- | :--- | :--- | :--- |
| 14 | [`fsi-credit-kyc-claims`](plugins/fsi-credit-kyc-claims/README.md) | Vertical | `commercial-credit-memo-analyst`, `kyc-aml-screening-dossier`, `insurance-claims-triage-pack` | BigQuery, KYB Registry API, Sheets; `fsi-credit-kyc-baseline.md` |
| 15 | [`industrial-shopfloor-maintenance`](plugins/industrial-shopfloor-maintenance/README.md) | Vertical | `asset-reliability-spares-planner`, `quality-capex-rca-copilot`, `ehs-safety-permit-auditor` | SAP PM/QM OData, BigQuery, Sheets; `finance-materiality-baseline.md`, `itsm-sla-severity-baseline.md` |
| 16 | [`healthcare-clinical-regulatory`](plugins/healthcare-clinical-regulatory/README.md) | Vertical | `clinical-protocol-feasibility`, `pharmacovigilance-safety-intake`, `prior-auth-medical-necessity` | BigQuery, Docs, Sheets, Drive; `itsm-sla-severity-baseline.md`, `commercial-contract-baseline.md` |
| 17 | [`retail-store-merchandising`](plugins/retail-store-merchandising/README.md) | Vertical | `store-ops-shrink-copilot`, `merchandising-assortment-planner`, `supplier-otif-chargeback-auditor` | BigQuery, SAP MM, Sheets, Drive; `finance-materiality-baseline.md`, `itsm-sla-severity-baseline.md` |
| 18 | [`marketplace-superapp-ops`](plugins/marketplace-superapp-ops/README.md) | Vertical | `merchant-catalog-trust-gate`, `logistics-sla-dispute-resolver`, `commission-payout-reconciler` | BigQuery, Marketplace REST API, Sheets; `itsm-sla-severity-baseline.md`, `finance-materiality-baseline.md` |
| 19 | [`telco-noc-field-dispatch`](plugins/telco-noc-field-dispatch/README.md) | Vertical | `noc-outage-topology-correlator`, `field-dispatch-spares-prep`, `b2b-order-fallout-resolver` | ServiceNow EM/FSM, BigQuery, Sheets; `itsm-sla-severity-baseline.md`, `finance-materiality-baseline.md` |
| 20 | [`public-sector-higher-ed`](plugins/public-sector-higher-ed/README.md) | Vertical | `citizen-case-eligibility-triager`, `procurement-tender-evaluator`, `grant-accreditation-evidence-pack` | ServiceNow CSM, BigQuery, Drive, Sheets; `commercial-contract-baseline.md`, `itsm-sla-severity-baseline.md` |

---

## Repository Architecture & Shared Knowledge

```text
gemini-agent-plugins/
├── .gemini-agent/catalog.json        # Machine-readable catalog of 20 plugins & 60 skills
├── shared/
│   ├── schema/                       # JSON Schemas (plugin, connectors, eval, catalog)
│   ├── traps/                        # 9 enterprise API & analytical trap guides
│   └── baselines/                    # 6 Day-1 industry baselines (Contracts, Finance, Deal Desk, ITSM, HR, FSI)
├── plugins/<plugin-id>/
│   ├── .gemini-plugin/
│   │   ├── plugin.json               # Plugin manifest, skill bindings, trap/baseline refs
│   │   ├── connectors.yaml           # 3-mode capability & connector declarations
│   │   ├── config.schema.json        # Typed JSON Schema with org_configured default false
│   │   └── policy.cel                # Read/draft/HITL mutation splits + CEL guardrails
│   ├── agents/<plugin-id>-coworker.yaml
│   ├── schedules/<cron-watch>.yaml   # Recurring cron templates with token cap & goal verifier
│   └── skills/<skill-id>/
│       ├── SKILL.md                  # Frontmatter + workflow + trap + HITL instructions
│       ├── TEST.md                   # Mode A/B/C test scenarios & assertions
│       ├── EVAL.yaml                 # Deterministic checks + weighted rubric
│       ├── scripts/<engine>.py       # Stdlib Python 3.11+ computation engine
│       └── references/               # Materialized traps, baselines, and default config.json
├── tools/                            # skill_validator.py, validate_repo.py, package.py
├── tests/                            # Synthetic enterprise fixtures & full pytest suite
└── dist/                             # 20 bundles + 60 skills + SHA-256 manifest.json
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed explanations of the 7 architectural pillars and [CONTRIBUTING.md](CONTRIBUTING.md) for plugin authoring and clean-room rules.

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
