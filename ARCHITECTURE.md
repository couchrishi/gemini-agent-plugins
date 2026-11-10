# Architecture of `gemini-agent-plugins`

This repository implements seven architectural pillars designed to eliminate common failure modes when deploying autonomous agents against enterprise systems of record.

## 1. Declarative Capabilities & 3-Mode Connector Degradation

Each plugin declares its integration needs inside `.gemini-plugin/connectors.yaml` (validated by [`shared/schema/connectors.schema.json`](shared/schema/connectors.schema.json)) using three progressive fallback tiers rather than brittle hard-coded API dependencies:

1. **Mode A — Live Enterprise Connectors:** Structured OAuth2 / mTLS / Workload Identity templates targeting SAP S/4HANA OData, ServiceNow Table/EM APIs, Salesforce SOQL, Workday RaaS, BigQuery, Looker, Jira, GitHub/GitLab, or Microsoft 365 SharePoint/OneDrive.
2. **Mode B — Google Workspace Fallback:** Read-only fallbacks into Google Drive, Docs (including Tabbed Docs), Sheets (`UNFORMATTED_VALUE`), Gmail, Calendar, and Meet exports when direct 3P enterprise connectors are unprovisioned.
3. **Mode C — Direct Local File Upload:** Zero-connector execution against user-uploaded `.json` or `.csv` snapshots read with `view_file` and processed directly in Python.

## 2. Typed Tenant Configuration & Day-1 Starter Baselines

Prompting an agent without thresholds causes arbitrary risk ratings. Conversely, hardcoding a single customer's rules breaks portability across organizations.

- Every plugin exposes a strict Draft 2020-12 JSON Schema at `.gemini-plugin/config.schema.json` with `"org_configured": { "default": false }` and safe numeric bounds.
- Six Day-1 starter rubrics live under [`shared/baselines/`](shared/baselines/):
  - [`commercial-contract-baseline.md`](shared/baselines/commercial-contract-baseline.md)
  - [`finance-materiality-baseline.md`](shared/baselines/finance-materiality-baseline.md)
  - [`deal-desk-approval-baseline.md`](shared/baselines/deal-desk-approval-baseline.md)
  - [`itsm-sla-severity-baseline.md`](shared/baselines/itsm-sla-severity-baseline.md)
  - [`hr-hiring-comp-baseline.md`](shared/baselines/hr-hiring-comp-baseline.md)
  - [`fsi-credit-kyc-baseline.md`](shared/baselines/fsi-credit-kyc-baseline.md)
- When `org_configured` is `false`, every computation engine automatically emits:
  `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`
- Running `tools/package.py --org-config <tenant.json>` validates tenant overrides against each plugin's `config.schema.json`, injects custom thresholds into `references/config.json` with `"org_configured": true`, stamps clean tenant-specific `.zip` bundles, and suppresses the baseline banner.

## 3. Persistent Python RAM Computation (`pyrepl` + CLI Parity)

LLMs should synthesize, verify policy context, and explain decisions—never perform multi-currency arithmetic, aging buckets, BOM explosions, cohort retention, or cumulative beneficial-ownership graph traversals inside token prediction.

- Every one of the 60 workflow skills executes a dedicated stdlib-first Python 3.11+ engine exporting `load_config`, `load_payload`, `analyze`, `render_markdown`, and an `argparse` `main` entrypoint (`--input`, `--config`, `--format json|markdown`, `--output`).
- Inside Gemini Agent, the model resolves the active skill folder under `/workspace/skills/<slug>/` (or `skills/user-skills/<slug>/`) inside persistent `pyrepl` RAM for iterative slice/dice exploration without losing state, falling back cleanly to `python3 "$SKILL_DIR/scripts/<module>.py"` when executed outside `pyrepl`.

## 4. Enterprise API & Analytical Trap Defenses

Enterprise SaaS APIs fail in predictable ways that silently corrupt LLM conclusions. Nine shared guides under [`shared/traps/`](shared/traps/) are materialized into every packaged skill and bundle:

| Trap Guide | Core Failure Mode Prevented |
| :--- | :--- |
| [`absent-is-not-zero.md`](shared/traps/absent-is-not-zero.md) | Treating truncated pagination, `top-N` cutoffs, unpolled terminals, or missing records as `$0` / clean compliance |
| [`chain-denominator-seams.md`](shared/traps/chain-denominator-seams.md) | Joining mismatched fiscal calendars, promo-vs-baseline durations, or pre-FX vs post-FX denominators |
| [`untrusted-content-and-pii.md`](shared/traps/untrusted-content-and-pii.md) | Following attacker instructions embedded inside external emails/tickets/catalog copy, wire-change fraud, and raw SSN/PHI echoing |
| [`google-workspace-traps.md`](shared/traps/google-workspace-traps.md) | Missing Shared Drive query flags, ignoring tabbed Google Docs tabs, or reading formatted Sheets strings instead of `UNFORMATTED_VALUE` |
| [`sharepoint-onedrive-kql-traps.md`](shared/traps/sharepoint-onedrive-kql-traps.md) | Unscoped site searches, broken SharePoint KQL syntax, and document-library pagination ceilings |
| [`servicenow-jira-itsm-traps.md`](shared/traps/servicenow-jira-itsm-traps.md) | Mixing numeric state enums vs `display_value`, broken `sys_id` joins, and wall-clock vs business-elapsed SLA timers |
| [`salesforce-crm-soql-traps.md`](shared/traps/salesforce-crm-soql-traps.md) | Confusing `StageName` probability vs `ForecastCategory`, ignoring `DatedConversionRate`, and polymorphic `WhoId`/`WhatId` lookups |
| [`bigquery-sap-erp-traps.md`](shared/traps/bigquery-sap-erp-traps.md) | Unfiltered BigQuery full-table scans, SAP `TCURR` inverted rates, `TCURX` 0-decimal JPY/KRW shifts, `SHKZG` sign inversions, and `GR/IR` timing |
| [`workday-hris-traps.md`](shared/traps/workday-hris-traps.md) | Counting future/historical effective-dated rows, double-counting Contingent Workers (`CWK`) in FTE totals, and small-cell `n < 5` re-identification |

## 5. Typed Tool Splits & CEL HITL Policy Gates

Every plugin separates execution permissions in `.gemini-plugin/policy.cel`:
- `read_only_tools`: safe data-retrieval and `pyrepl` read operations.
- `draft_only_tools`: local artifacts, redlines, Memos, PR drafts, or Doc/Sheet creation without external side effects.
- `hitl_gated_mutations`: external mutations (ERP postings, wire transfers, credit commitments, SAR filings, vendor debit memos, P1 incident broadcasts, safety permit sign-offs) tagged with explicit CEL boolean conditions (`task_sticky` or `explicit_per_call`) and validated by the recursive-descent CEL parser in [`tools/validate_repo.py`](tools/validate_repo.py).

## 6. Native Recurring Schedules & Goal Verifiers

Each plugin defines a `ScheduleTemplate` under `plugins/<id>/schedules/*.yaml` encoding a standard 5-field `cron_expression`, an explicit `max_token_budget` ceiling, a `target_skill`, and a dual `goal_verifier`:
- `command_check`: deterministic CLI/script sanity command.
- `nl_criteria`: concrete post-run acceptance predicates checked against output artifacts.

## 7. Dual Packaging & Dual-Mode CI Evaluation

[`tools/package.py`](tools/package.py) preserves a single source of truth while generating two ready-to-upload formats:
- `dist/bundles/<plugin-id>.zip` (20 archives): synthesizes a root router `SKILL.md`, rewrites relative workflow links into `references/workflows/<skill-id>.md`, bundles all 3 scripts, `config.json`, traps, and baselines.
- `dist/skills/<skill-id>.zip` (60 archives): packages each individual skill verbatim with only the traps and baselines declared by its parent plugin.

[`tools/validate_repo.py`](tools/validate_repo.py) and `EVAL.yaml` enforce schema validity, exact relative Markdown link bijections across all 140 `SKILL.md` contexts (60 source + 60 skill zips + 20 bundle zips), CEL grammar, AST non-stub enforcement, deterministic `dist/manifest.json` SHA-256 verification, and public clean-room hygiene across source files, packaged `.zip` internals, and `git log`.
