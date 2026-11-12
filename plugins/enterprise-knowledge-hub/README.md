# Enterprise Knowledge Hub (`enterprise-knowledge-hub`)

Synthesizes cross-source enterprise knowledge with strict citation conflict detection, jurisdiction-scoped SOP/policy answering with abstention gates, and corpus freshness/duplication auditing across Google Workspace, SharePoint, and Confluence. Pairs live `/work` connectors (`Google Drive, Google Docs, Google Sheets, Microsoft 365 (SharePoint, OneDrive, Outlook, Teams), Confluence, ServiceNow, Slack`) with `pyrepl` header inspection and Python payload shaping, three deterministic Python 3.11+ standard-library engines, typed JSON Schema thresholds (`org_configured: false` baseline), and `Auto-Guardian` write governance.

## Personas & Workflows

| Role / Persona | Business Trigger | Workflow Skill | Deterministic Engine |
| :--- | :--- | :--- | :--- |
| Knowledge Operations Lead | Reconciling conflicting guidance across Drive, SharePoint, and Confluence | [`cross-source-knowledge-synthesis`](skills/cross-source-knowledge-synthesis/README.md) | `scripts/citation_conflict_auditor.py` |
| HR & Workplace Partner | Answering country- or entity-specific leave, stipend, or SOP inquiries | [`policy-sop-answering`](skills/policy-sop-answering/README.md) | `scripts/policy_scope_matcher.py` |
| Intranet & Confluence Owner | Running Monday corpus hygiene sweeps before quarterly internal audits | [`knowledge-gap-freshness-audit`](skills/knowledge-gap-freshness-audit/README.md) | `scripts/corpus_hygiene_scanner.py` |

## Choosing an Archive: Bundle vs. Individual Skill

- **Department Bundle ([`enterprise-knowledge-hub.zip`](../../dist/bundles/enterprise-knowledge-hub.zip))**: Best for general department workspaces needing all three related workflows, shared trap guides, starter baselines, and unified `references/config.json`.
- **Individual Skill (`dist/skills/<skill-id>.zip`)**: Best for tight single-workflow agents needing minimal context overhead:
  - [`dist/skills/cross-source-knowledge-synthesis.zip`](../../dist/skills/cross-source-knowledge-synthesis.zip) — Scores source authority and recency across multi-repo hits, flags conflicting numerical/date claims, and verifies 100% claim citation coverage.
  - [`dist/skills/policy-sop-answering.zip`](../../dist/skills/policy-sop-answering.zip) — Filters policy and SOP clauses by jurisdiction, entity, and effective date, enforcing abstention when active coverage is missing.
  - [`dist/skills/knowledge-gap-freshness-audit.zip`](../../dist/skills/knowledge-gap-freshness-audit.zip) — Audits Drive, SharePoint, and Confluence inventories for overdue review dates, departed owners, near-duplicate titles, and unindexed ticket gaps.

## Quickstart: Gemini Enterprise (`/work`), `pyrepl` & CLI

1. **Upload in `/work`**: Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select [`enterprise-knowledge-hub.zip`](../../dist/bundles/enterprise-knowledge-hub.zip) -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
2. **Run Against Live Connectors (Primary)**: Prompt Gemini naturally or invoke `/enterprise-knowledge-hub` / `@enterprise-knowledge-hub` so Layer 1 (`remote_cli mcp`) pulls live data from `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack`.
3. **Adapt Custom Exports in `pyrepl` or Test Locally**: For custom customer workbooks or JSON payloads, inspect detected tabs/keys via `shared/scripts/enterprise_io.py` in `pyrepl` and shape rows into a canonical `payload` dict in 5-10 lines of Python before calling `analyze(payload, config=...)`. To verify locally with [`Apex_Policy_SOP_and_KB_Sample.docx` (`4,201 B`, `.docx` document with `7` embedded tables)](../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx):

```bash
python3 plugins/enterprise-knowledge-hub/skills/cross-source-knowledge-synthesis/scripts/citation_conflict_auditor.py \
  --input examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx \
  --config plugins/enterprise-knowledge-hub/skills/cross-source-knowledge-synthesis/references/config.json \
  --format markdown
```

Bind custom organizational thresholds (materiality limits, SLA budgets, covenant floors) without editing repository source files:

```bash
python3 tools/package.py --org-config tests/fixtures/sample_org_config.json --output-dir /tmp/custom-dist
```

## Connectors, Schema Normalization & Governance

- **Managed 1P Connectors (`/work`)**: `Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack`.
- **Connector Fetch Guidance**: Retrieve authoritative policy docs, multi-tab Google Docs (includeTabsContent=true), SharePoint libraries, Confluence pages, and ServiceNow KB articles via remote_cli mcp before ranking authority and freshness in Python.
- **Connected Docs & Sandbox Fallback**: Supports Google Drive, Google Sheets (`UNFORMATTED_VALUE`), Google Docs (`includeTabsContent=true`), SharePoint/OneDrive (`@odata.nextLink`), and local `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` files via [`shared/scripts/enterprise_io.py`](../../shared/scripts/enterprise_io.py). Sandbox starter: [`Apex_Policy_SOP_and_KB_Sample.docx` (`4,201 B`, `.docx` document with `7` embedded tables)](../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx).
- **Schema Normalization & Baseline Config**: Governed by [`config.schema.json`](.gemini-plugin/config.schema.json) (`org_configured: false` stamps `[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]`). Inside `pyrepl`, agents inspect source headers first and normalize messy customer tables cleanly in Python before running deterministic engines.
- **Shared Baselines & Trap Guides**: [`itsm-sla-severity-baseline.md`](../../shared/baselines/itsm-sla-severity-baseline.md), [`commercial-contract-baseline.md`](../../shared/baselines/commercial-contract-baseline.md) and [`absent-is-not-zero.md`](../../shared/traps/absent-is-not-zero.md), [`google-workspace-traps.md`](../../shared/traps/google-workspace-traps.md), [`sharepoint-onedrive-kql-traps.md`](../../shared/traps/sharepoint-onedrive-kql-traps.md), [`untrusted-content-and-pii.md`](../../shared/traps/untrusted-content-and-pii.md).
- **Agent Gateway (`Auto-Guardian`) Approval Actions**: Publishing or overwriting authoritative SOP pages in Confluence or ServiceNow KB; Archiving or deleting stale documents in SharePoint or Google Drive; Broadcasting corpus hygiene audit digests to Slack channels or email distribution lists.
- **Code-Enforced Python Guardrails (`scripts/*.py`)**: Strict fail-closed abstention on 403 permission errors or zero jurisdiction matches (UNVERIFIED_INSUFFICIENT_SCOPE); Published vs superseded/draft version authority precedence and departed-owner flagging; Contradictory cross-source numeric/SLA threshold surfacing rather than silent averaging.
- **Conversational Scheduling (`schedule_task`)**: Ask chat: *"Schedule recurring job "Weekly Corpus Hygiene Audit" on cron `0 7 * * 1` (`UTC`) with instruction: "Run the weekly enterprise knowledge hygiene scan across Drive, SharePoint, and Confluence metadata exports. Execute scripts/corpus_hygiene_scanner.py against the latest corpus inventory and ticket-topic gap feed, highlight stale/unreviewed SOPs, departed owners, unpublished minor versions, and top unindexed support topics, and draft a remediation sheet for owner confirmation without archiving any file automatically.""*

## Example Queries & Verified Outcomes

- **`cross-source-knowledge-synthesis`** ([skill guide](skills/cross-source-knowledge-synthesis/README.md)): Connector prompt: *"Search Drive, SharePoint, and Confluence for Cymbal Financial's current remote-work expense stipend and flag any contradictory figures across decks vs official HR policy."* Verified starter check against `Apex_Policy_SOP_and_KB_Sample.docx` (`161.1 ms`): `source_count=3`, `total_available=3`, `truncated=False`, `conflict_topic_count=1`.
- **`policy-sop-answering`** ([skill guide](skills/policy-sop-answering/README.md)): Connector prompt: *"What is Apex Manufacturing's parental leave duration in Singapore as of 2026-11-10? Check SharePoint and Drive policies."* Verified starter check against `Apex_Policy_SOP_and_KB_Sample.docx` (`147.8 ms`): `evaluated_clauses=4`, `active_clause_count=1`, `rejected_clause_count=3`, `abstained=False`.
- **`knowledge-gap-freshness-audit`** ([skill guide](skills/knowledge-gap-freshness-audit/README.md)): Connector prompt: *"Run a quarterly hygiene audit across our SharePoint SOP library and ServiceNow L1 ticket topics to find stale SOPs and top undocumented issues."* Verified starter check against `Apex_Policy_SOP_and_KB_Sample.docx` (`154.1 ms`): `documents_scanned=4`, `total_available=4`, `truncated=False`, `stale_count=2`.

## Benchmark Reference

Evaluated on unguided multi-surface benchmark **`PE-10`** (`26-page .docx + 28-page PDF`) in [`benchmarks/EVALUATION.md`](../../benchmarks/EVALUATION.md): `gemini-agent-plugins` scored **`PASS (0.973 comp / 1.000 WF)`** vs `Base Agent (No Plugin)` (`PASS 0.884 / 1.000`) and `Prose-Only Baseline` (`PASS 0.883 / 1.000`). Verified domain traps: Version & status precedence (published v3.2 vs retired v1.8); Stale review date + departed owner detection (KB-SSO-014); SOC2/GDPR cold-storage erasure lag (CTRL-GDPR-17).
