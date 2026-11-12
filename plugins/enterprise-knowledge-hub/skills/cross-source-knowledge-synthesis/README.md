# Cross-Source Knowledge Synthesis (`cross-source-knowledge-synthesis`)

Synthesizes cross-source answers across Drive, SharePoint, and Confluence, ranking authority and detecting conflicting numerical/date claims with 100% citation verification. Deterministic computation executes via [`scripts/citation_conflict_auditor.py`](scripts/citation_conflict_auditor.py). Domain guards enforced: Detects truncated search results via total_available > source_count; Quarantines embedded indirect prompt injection strings in excerpts. Direct local uploads support `.xlsx`, `.docx`, `.csv`, `.tsv`, `.json`, `.jsonl` via `scripts/enterprise_io.py` (zero third-party Excel/Word dependencies; pass `--sheet <TabName>` or `sheet="..."` to target a single worksheet).

## Who Uses This

- **Knowledge Operations Lead**: Triggered when reconciling conflicting guidance across Drive, SharePoint, and Confluence; selects the authoritative source version and reconciles numeric policy drift.
- **Security & Compliance Reviewer**: Triggered when verifying policy answers before publishing executive digests; confirms 100% claim-level citation coverage and quarantines prompt injections.

## Step-by-Step Usage (`Gemini Enterprise /work`)

### Upload & Run in Gemini Enterprise (`/work`)

1. Download the single-hop skill archive [`cross-source-knowledge-synthesis.zip`](../../../../dist/skills/cross-source-knowledge-synthesis.zip) (or the full department bundle [`enterprise-knowledge-hub.zip`](../../../../dist/bundles/enterprise-knowledge-hub.zip)).
2. Open **Gemini Enterprise web app (`/work`) -> left navigation `Skills` -> `+` -> `Upload skill` -> select `.zip` -> `Import`** (Standard, Plus, or Pay-as-you-go edition).
3. Ensure your enterprise connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack`) are authorized in your workspace, or attach a Drive/SharePoint export or optional sandbox starter file [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx).
4. Ask naturally in chat or invoke directly with `/cross-source-knowledge-synthesis` or `@cross-source-knowledge-synthesis`; review the synthesized chat summary and `Auto-Guardian` confirmation prompt before any external write runs.

### Adapting to Custom Customer Schemas (Inspect & Shape in Python)

Customer exports and live connector payloads often use unfamiliar worksheet tab names, column headers, or nested keys. Inside `pyrepl`, read the source via `scripts/enterprise_io.py`, inspect actual tabs and headers in Python, and normalize mismatched fields into a canonical `payload` dict in 5-10 lines before calling `analyze(payload, config=...)`:

```python
from pathlib import Path
from scripts.enterprise_io import read_docx
from scripts.citation_conflict_auditor import analyze, render_markdown

doc = read_docx(Path("customer_document.docx"))
print([(t.get("headers"), len(t.get("rows", []))) for t in doc.get("tables", [])])

# Pass standard .docx directly, or normalize custom tables into a canonical dict:
payload = {"sources": [{"id": r.get("Source id"), "title": r.get("Source title")} for r in doc["tables"][0]["rows"]]}
result = analyze(payload, config=Path("references/config.json"))
print(render_markdown(result))
```

You can also bind organization-wide thresholds cleanly via `python3 tools/package.py --org-config org.json`.

### Local CLI Verification

Run the deterministic computation engine locally from the repository root with zero external dependencies:

```bash
python3 plugins/enterprise-knowledge-hub/skills/cross-source-knowledge-synthesis/scripts/citation_conflict_auditor.py \
  --input examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx \
  --config plugins/enterprise-knowledge-hub/skills/cross-source-knowledge-synthesis/references/config.json \
  --format markdown
```

Pass `--sheet <TabName>` to `citation_conflict_auditor.py` when targeting a specific worksheet in multi-tab `.xlsx` workbooks.

## Sample Queries

1. **Primary — Live Enterprise Connectors (`Google Drive`, `Google Docs`, `Google Sheets`, `Microsoft 365 (SharePoint, OneDrive, Outlook, Teams)`, `Confluence`, `ServiceNow`, `Slack` via `remote_cli mcp`):** "Search Drive, SharePoint, and Confluence for Cymbal Financial's current remote-work expense stipend and flag any contradictory figures across decks vs official HR policy."
2. **Connected Drive / SharePoint Workbooks & Docs:** "SharePoint connector is disabled; synthesize the Q4 procurement approval limits from our Shared Drive Google Docs and Sheets and tell me if any scope is missing."
3. **Optional Zero-Connector Sandbox Test:** Attach [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx) and ask: "Using the attached `Apex_Policy_SOP_and_KB_Sample.docx` dossier, rank our multi-repo knowledge sources by authority and publish status, flag any contradictory policy claims across versions, quarantine untrusted prompt injections, and verify whether draft claims meet 100% citation coverage."

## Sample Response

### What You See in Gemini Enterprise Chat

Across the `3` knowledge hits in `Apex_Policy_SOP_and_KB_Sample.docx`, published Confluence record `SRC-SEC-99` (SOC2 Backup Erasure Addendum, authority score `0.7742`) outranks draft `SRC-CONF-32` (`0.1966`) and retired `SRC-DRV-18` (`0.1429`), while citation coverage sits at `0.0%` across `3` uncited draft claims (`citation_gate_passed: False`).

- **Authoritative Winner:** `SRC-SEC-99` overrides lower-authority and draft travel/expense records (`SRC-CONF-32`, `SRC-DRV-18`) across `1` conflicting topic (`general`).
- **Publication Gate Held:** `3` draft claims lack explicit source IDs (`citation_coverage_pct = 0.0%`), failing the `100%` citation requirement even though `0` prompt injections were active.
- **Approval Confirmation Prompt:** Confirm if you would like to publish the synthesized Confluence revision with attached `SRC-SEC-99` citations via your connected `Confluence` connector (gated by `Auto-Guardian`), or approve broadcasting a summary digest via your connected `Slack` or `Gmail` / `Outlook` connector once citations reach `100%`.

### Verified Deterministic Engine Output

Executed directly against [`Apex_Policy_SOP_and_KB_Sample.docx`](../../../../examples/enterprise-knowledge-hub/Apex_Policy_SOP_and_KB_Sample.docx) (`161.1 ms`, `org_configured: false` baseline):

```markdown
[EVALUATED AGAINST STANDARD BASELINE — BIND ORG CONFIG TO CUSTOMIZE]

# Cross-Source Knowledge Synthesis Audit

- **Sources Ranked:** 3 / 3 (Truncated: `False`)
- **Top Authoritative Source:** `SRC-SEC-99`
- **Conflicting Topics Flagged:** 1
- **Citation Coverage:** 0.0% (Gate Passed: `False`)

## Source Authority Ranking

| Source ID | Title | Repo | Type | Modified | Draft | Score |
| :--- | :--- | :--- | :--- | :--- | :--- | ---: |
| `SRC-SEC-99` | SOC2 Backup Erasure Addendum | confluence | knowledge_article | 2026-09-20 | `False` | 0.7742 |
| `SRC-CONF-32` | US Corporate Travel Lodging Standard v3.2 | confluence | knowledge_article | 2026-10-15 | `True` | 0.1966 |
| `SRC-DRV-18` | Travel Expense Draft Notes v1.8 | drive | knowledge_article | 2024-06-01 | `True` | 0.1429 |

## Detected Contradictions

- **Topic `general`:** Prefer SRC-SEC-99 (knowledge_article, score=0.7742) over lower-authority/older variants.
```

## Automation Schedule (`schedule_task`)

When you want recurring monitoring in Gemini Enterprise (`/work`), ask chat to schedule the `Weekly Corpus Hygiene Audit` routine via `schedule_task`:

```text
Schedule recurring job "Weekly Corpus Hygiene Audit" on cron `0 7 * * 1` (`UTC`) with instruction: "Run the weekly enterprise knowledge hygiene scan across Drive, SharePoint, and Confluence metadata exports. Execute scripts/corpus_hygiene_scanner.py against the latest corpus inventory and ticket-topic gap feed, highlight stale/unreviewed SOPs, departed owners, unpublished minor versions, and top unindexed support topics, and draft a remediation sheet for owner confirmation without archiving any file automatically."
```

## Input Fields & Configurable Thresholds

- **Data Contract Inputs:** `as_of_date`, `sources`, `draft_claims`; optional `metadata` (`truncated`, `done`, `total_available`)
- **Required Canonical Field Groups:** `sources` requires [`id` or `doc_id` or `source_id`; `title` or `name`] | `draft_claims` requires [`claim_id` or `id`; `statement` or `text`]

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `org_configured` | `boolean` | `false` | Set `true` by `tools/package.py --org-config` to suppress starter baseline banner |
| `recency_half_life_days` | `integer` | `365` | Exponential decay half-life in days when ranking document freshness. |
| `min_citation_coverage_pct` | `number` | `100.0` | Required percentage of synthesized claims backed by verified source IDs. |
| `allow_draft_versions_in_answers` | `boolean` | `False` | Whether unpublished draft SOP versions (e.g. SharePoint minor 1.2) may be cited as authoritative. |
| `authoritative_source_weights` | `object` | `{"official_policy": 1.0, "approved_sop": 0.9, "knowledge_art...` | Authority weighting by document classification. |

See [`../../README.md`](../../README.md) for the `enterprise-knowledge-hub` department playbook or [`SKILL.md`](SKILL.md) for full execution instructions.
